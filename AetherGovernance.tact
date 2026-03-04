// ============================================================
// AetherGovernance.tact — Contract 3/3: Timelock + Governance
//
// Responsibilities:
//   ✅ 48h Timelock on all parameter changes
//   ✅ 7-day action expiry (stale actions cannot be executed)
//   ✅ ProposeAction — owner or registered proposers
//   ✅ CancelAction — owner or original proposer
//   ✅ ExecuteAction → dispatches UpdateParams to Vault or Oracle
//   ✅ Vault and Oracle accept updates ONLY from governance_address
//   ✅ Proposer registry — extensible path toward DAO voting
//   ✅ 2-step ownership transfer
//   ✅ CEI pattern throughout
//
// Supported action types:
//   1 = SetVaultFee          (fee_bps)
//   2 = SetOracleMinSigs     (min_signatures)
//   3 = SetGuardianThreshold (threshold in coins)
//   4 = PauseVault
//   5 = UnpauseVault
//   6 = SetOracleFee         (fee_bps)
//   7 = PauseOracle
//   8 = UnpauseOracle
// ============================================================

import "@stdlib/deploy";

// ============================================================
// CONSTANTS
// ============================================================

const TIMELOCK_DELAY: Int = 172800;  // 48 hours
const ACTION_EXPIRY:  Int = 604800;  // 7 days — after this window, action is cancelled
const GAS_FWD:        Int = ton("0.05");
const MAX_FEE_BPS:    Int = 500;     // 5% hard cap
const MIN_SIGS_FLOOR: Int = 2;

// ============================================================
// OUTGOING UPDATE MESSAGES
// Sent to Vault or Oracle after timelock passes
// Vault / Oracle accept ONLY if sender() == governance_address
// ============================================================

message UpdateVaultFee          { new_fee_bps: Int as uint16; }
message UpdateGuardianThreshold { new_threshold: Int as coins; }
message UpdateOracleMinSigs     { new_min: Int as uint8; }
message UpdateOracleFee         { new_fee_bps: Int as uint16; }

// ============================================================
// GOVERNANCE MESSAGES
// ============================================================

message ProposeAction     { action_type: Int as uint8; param_int: Int as uint64; description: String; }
message CancelAction      { action_id: Int as uint256; }
message ExecuteAction     { action_id: Int as uint256; }
message AddProposer       { proposer: Address; }
message RemoveProposer    { proposer: Address; }
message TransferOwnership { new_owner: Address; }
message AcceptOwnership   {}

// ============================================================
// STRUCTS
// ============================================================

struct GovernanceAction {
    action_id:   Int as uint256;
    action_type: Int as uint8;
    param_int:   Int as uint64;
    description: String;
    proposed_by: Address;
    proposed_at: Int as uint64;
    ready_at:    Int as uint64;   // Earliest execution time (proposed_at + 48h)
    expires_at:  Int as uint64;   // Latest execution time (ready_at + 7 days)
    executed:    Bool;
    cancelled:   Bool;
}

// ============================================================
// EVENTS
// ============================================================

message(0x20) EvtActionProposed  { action_id: Int as uint256; action_type: Int as uint8; ready_at: Int as uint64; description: String; proposed_by: Address; }
message(0x21) EvtActionCancelled { action_id: Int as uint256; cancelled_by: Address; }
message(0x22) EvtActionExecuted  { action_id: Int as uint256; action_type: Int as uint8; }
message(0x23) EvtActionExpired   { action_id: Int as uint256; }
message(0x24) EvtOwnershipStarted { pending_owner: Address; }
message(0x25) EvtOwnershipDone   { old_owner: Address; new_owner: Address; }
message(0x26) EvtProposerAdded   { proposer: Address; }
message(0x27) EvtProposerRemoved { proposer: Address; }
message(0x28) EvtParamDispatched { action_id: Int as uint256; target: Address; action_type: Int as uint8; }

// ============================================================
// CONTRACT
// ============================================================

contract AetherGovernance with Deployable {

    owner:         Address;
    pending_owner: Address?;

    // Addresses of the contracts this Governance controls
    vault_address:  Address;
    oracle_address: Address;

    // Proposer registry — owner by default, extend for DAO
    proposers: map<Address, Bool>;

    // Timelock queue — keyed by action_id (uint256 hash)
    actions:      map<Int, GovernanceAction>;
    action_nonce: Int as uint64;  // Monotonic counter for unique action_id generation

    // ============================================================
    init(owner: Address, vault: Address, oracle: Address) {
        self.owner          = owner;
        self.pending_owner  = null;
        self.vault_address  = vault;
        self.oracle_address = oracle;
        self.action_nonce   = 0;
    }

    // ============================================================
    // PROPOSE — queue an action into the timelock
    // ============================================================

    receive(msg: ProposeAction) {
        let caller: Address = sender();
        require(
            caller == self.owner || self.proposers.get(caller) == true,
            "Not authorized to propose"
        );

        // Validate param against action type before queuing
        if (msg.action_type == 1 || msg.action_type == 6) {
            require(msg.param_int <= MAX_FEE_BPS, "Fee exceeds 5% hard cap");
        }
        if (msg.action_type == 2) {
            require(msg.param_int >= MIN_SIGS_FLOOR, "min_sigs must be >= 2");
        }
        if (msg.action_type == 3) {
            require(msg.param_int > 0, "Guardian threshold must be > 0");
        }
        require(
            msg.action_type >= 1 && msg.action_type <= 8,
            "Unknown action_type — valid range: 1–8"
        );

        // Generate unique action_id from nonce + proposer + timestamp
        self.action_nonce = self.action_nonce + 1;
        let action_id: Int = beginCell()
            .storeUint(self.action_nonce, 64)
            .storeAddress(caller)
            .storeUint(now(), 64)
        .endCell().hash();

        let ready_at:   Int = now() + TIMELOCK_DELAY;
        let expires_at: Int = ready_at + ACTION_EXPIRY;

        self.actions.set(action_id, GovernanceAction {
            action_id:   action_id,
            action_type: msg.action_type,
            param_int:   msg.param_int,
            description: msg.description,
            proposed_by: caller,
            proposed_at: now(),
            ready_at:    ready_at,
            expires_at:  expires_at,
            executed:    false,
            cancelled:   false,
        });

        emit(EvtActionProposed {
            action_id:   action_id,
            action_type: msg.action_type,
            ready_at:    ready_at,
            description: msg.description,
            proposed_by: caller,
        }.toCell());
    }

    // ============================================================
    // CANCEL — remove action before execution
    // ============================================================

    receive(msg: CancelAction) {
        let caller: Address           = sender();
        let action: GovernanceAction? = self.actions.get(msg.action_id);

        require(action != null,      "Action not found");
        require(!action!!.executed,  "Action already executed");
        require(!action!!.cancelled, "Action already cancelled");
        require(
            caller == self.owner || caller == action!!.proposed_by,
            "Only owner or original proposer can cancel"
        );

        self.actions.set(msg.action_id, GovernanceAction {
            action_id:   action!!.action_id,
            action_type: action!!.action_type,
            param_int:   action!!.param_int,
            description: action!!.description,
            proposed_by: action!!.proposed_by,
            proposed_at: action!!.proposed_at,
            ready_at:    action!!.ready_at,
            expires_at:  action!!.expires_at,
            executed:    false,
            cancelled:   true,
        });

        emit(EvtActionCancelled { action_id: msg.action_id, cancelled_by: caller }.toCell());
    }

    // ============================================================
    // EXECUTE — dispatch UpdateParams after timelock passes
    // ============================================================

    receive(msg: ExecuteAction) {
        self._assert_owner();

        let action: GovernanceAction? = self.actions.get(msg.action_id);
        require(action != null,      "Action not found");
        require(!action!!.executed,  "Action already executed");
        require(!action!!.cancelled, "Action is cancelled");
        require(now() >= action!!.ready_at, "Timelock not ready — wait 48 hours");

        // Check expiry — mark as cancelled and emit event, do not dispatch
        if (now() > action!!.expires_at) {
            self.actions.set(msg.action_id, GovernanceAction {
                action_id:   action!!.action_id,
                action_type: action!!.action_type,
                param_int:   action!!.param_int,
                description: action!!.description,
                proposed_by: action!!.proposed_by,
                proposed_at: action!!.proposed_at,
                ready_at:    action!!.ready_at,
                expires_at:  action!!.expires_at,
                executed:    false,
                cancelled:   true,
            });
            emit(EvtActionExpired { action_id: msg.action_id }.toCell());
            return;
        }

        // CEI: mark executed BEFORE dispatching messages
        self.actions.set(msg.action_id, GovernanceAction {
            action_id:   action!!.action_id,
            action_type: action!!.action_type,
            param_int:   action!!.param_int,
            description: action!!.description,
            proposed_by: action!!.proposed_by,
            proposed_at: action!!.proposed_at,
            ready_at:    action!!.ready_at,
            expires_at:  action!!.expires_at,
            executed:    true,
            cancelled:   false,
        });

        self._dispatch(action!!.action_type, action!!.param_int, msg.action_id);

        emit(EvtActionExecuted {
            action_id: msg.action_id, action_type: action!!.action_type,
        }.toCell());
    }

    // ============================================================
    // DISPATCH — route UpdateParams to the correct target contract
    // Vault and Oracle validate sender() == governance_address
    // ============================================================

    fun _dispatch(action_type: Int, param: Int, action_id: Int) {

        // ── Vault targets ────────────────────────────────────────

        if (action_type == 1) {
            send(SendParameters {
                to: self.vault_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: UpdateVaultFee { new_fee_bps: param }.toCell(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.vault_address, action_type: action_type }.toCell());
        }

        if (action_type == 3) {
            send(SendParameters {
                to: self.vault_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: UpdateGuardianThreshold { new_threshold: param }.toCell(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.vault_address, action_type: action_type }.toCell());
        }

        if (action_type == 4) {
            send(SendParameters {
                to: self.vault_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: "pause".asComment(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.vault_address, action_type: action_type }.toCell());
        }

        if (action_type == 5) {
            send(SendParameters {
                to: self.vault_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: "unpause".asComment(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.vault_address, action_type: action_type }.toCell());
        }

        // ── Oracle targets ───────────────────────────────────────

        if (action_type == 2) {
            send(SendParameters {
                to: self.oracle_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: UpdateOracleMinSigs { new_min: param }.toCell(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.oracle_address, action_type: action_type }.toCell());
        }

        if (action_type == 6) {
            send(SendParameters {
                to: self.oracle_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: UpdateOracleFee { new_fee_bps: param }.toCell(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.oracle_address, action_type: action_type }.toCell());
        }

        if (action_type == 7) {
            send(SendParameters {
                to: self.oracle_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: "pause".asComment(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.oracle_address, action_type: action_type }.toCell());
        }

        if (action_type == 8) {
            send(SendParameters {
                to: self.oracle_address, value: GAS_FWD, mode: SendIgnoreErrors,
                body: "unpause".asComment(),
            });
            emit(EvtParamDispatched { action_id: action_id, target: self.oracle_address, action_type: action_type }.toCell());
        }
    }

    // ============================================================
    // PROPOSER MANAGEMENT
    // ============================================================

    receive(msg: AddProposer) {
        self._assert_owner();
        self.proposers.set(msg.proposer, true);
        emit(EvtProposerAdded { proposer: msg.proposer }.toCell());
    }

    receive(msg: RemoveProposer) {
        self._assert_owner();
        require(self.proposers.get(msg.proposer) == true, "Not a registered proposer");
        self.proposers.set(msg.proposer, false);
        emit(EvtProposerRemoved { proposer: msg.proposer }.toCell());
    }

    // ============================================================
    // OWNERSHIP — 2-step transfer
    // ============================================================

    receive(msg: TransferOwnership) {
        self._assert_owner();
        require(msg.new_owner != self.owner, "Already owner");
        self.pending_owner = msg.new_owner;
        emit(EvtOwnershipStarted { pending_owner: msg.new_owner }.toCell());
    }

    receive(msg: AcceptOwnership) {
        require(self.pending_owner != null,       "No pending ownership transfer");
        require(sender() == self.pending_owner!!, "Sender is not pending owner");
        let old: Address   = self.owner;
        self.owner         = self.pending_owner!!;
        self.pending_owner = null;
        emit(EvtOwnershipDone { old_owner: old, new_owner: self.owner }.toCell());
    }

    // ============================================================
    // GETTERS
    // ============================================================

    get fun owner_address():  Address { return self.owner; }
    get fun vault_addr():     Address { return self.vault_address; }
    get fun oracle_addr():    Address { return self.oracle_address; }
    get fun action_count():   Int     { return self.action_nonce; }

    get fun is_proposer(a: Address): Bool {
        return a == self.owner || self.proposers.get(a) == true;
    }

    get fun get_action(id: Int): GovernanceAction? {
        return self.actions.get(id);
    }

    get fun is_ready(id: Int): Bool {
        let a: GovernanceAction? = self.actions.get(id);
        if (a == null) { return false; }
        return !a!!.executed && !a!!.cancelled
            && now() >= a!!.ready_at
            && now() <= a!!.expires_at;
    }

    // ============================================================
    // INTERNAL
    // ============================================================

    fun _assert_owner() { require(sender() == self.owner, "Not owner"); }
}
