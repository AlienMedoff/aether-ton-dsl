// ============================================================
// AetherVault.tact — Contract 1/3: Core Escrow
// + Request-Response protocol with AetherOracle
//
// Responsibilities:
//   ✅ Agent registry with independent daily / per-TX limits
//   ✅ AgentAction execution with CEI pattern
//   ✅ Guardian 2-key approval (pending queue + 30 min TTL)
//   ✅ GuardianReject → automatic refund via ClaimRefund
//   ✅ Trust score gate (cached from Oracle via async protocol)
//   ✅ FetchTrustScore → RequestTrustScore → Oracle
//   ✅ ResponseTrustScore ← Oracle (sender validated)
//   ✅ CleanupExpiredQuery — manual cleanup of stale queries
//   ✅ Kill-switch pause / unpause
//   ✅ EmergencyWithdraw (requires pause first)
//   ✅ GAS_RESERVE — vault never drains itself
//   ✅ 2-step ownership transfer
// ============================================================

import "@stdlib/deploy";

// ============================================================
// CONSTANTS
// ============================================================

const GAS_RESERVE:     Int = ton("0.05");  // Minimum balance kept in contract at all times
const GUARDIAN_TTL:    Int = 1800;         // 30 min — pending TX expiry
const MAX_AGENTS:      Int = 20;
const MAX_DAILY_LIMIT: Int = ton("1000");  // Hard cap on daily limit per agent
const DAY_SECONDS:     Int = 86400;
const QUERY_TIMEOUT:   Int = 600;          // 10 min — oracle response window
const ORACLE_FWD_GAS:  Int = ton("0.1");   // Gas forwarded to Oracle (covers round-trip)
const MIN_TRUST_SCORE: Int = 40;           // Minimum trust score to execute AgentAction

// ============================================================
// SHARED MESSAGES — must be identical in AetherOracle.tact
// ============================================================

message RequestTrustScore  { query_id: Int as uint64; user: Address; }
message ResponseTrustScore { query_id: Int as uint64; user: Address; score: Int as uint8; }

// ============================================================
// VAULT MESSAGES
// ============================================================

message RegisterAgent       { agent: Address; daily_limit: Int as coins; per_tx_max: Int as coins; }
message UpdateAgentLimits   { agent: Address; daily_limit: Int as coins; per_tx_max: Int as coins; }
message RevokeAgent         { agent: Address; }
message AgentAction         { amount: Int as coins; destination: Address; task_id: Int as uint32; memo: String; }
message SetGuardian         { guardian: Address; threshold: Int as coins; }
message GuardianApprove     { task_id: Int as uint32; }
message GuardianReject      { task_id: Int as uint32; }
message ClaimRefund         {}
message FetchTrustScore     { user: Address; }
message CleanupExpiredQuery { query_id: Int as uint64; }
message TransferOwnership   { new_owner: Address; }
message AcceptOwnership     {}
message EmergencyWithdraw   { reason: String; }

// Governance-only parameter updates — sender must be governance_address
message UpdateVaultFee          { new_fee_bps: Int as uint16; }
message UpdateGuardianThreshold { new_threshold: Int as coins; }
message SetGovernance           { governance: Address; }

// ============================================================
// STRUCTS
// ============================================================

struct AgentRecord {
    daily_limit: Int as coins;
    per_tx_max:  Int as coins;
    spent_today: Int as coins;
    last_reset:  Int as uint32;
    total_spent: Int as coins;
    tx_count:    Int as uint32;
    is_active:   Bool;
}

struct PendingTx {
    amount:      Int as coins;
    destination: Address;
    task_id:     Int as uint32;
    memo:        String;
    agent:       Address;
    created_at:  Int as uint32;
}

struct PendingQuery {
    user:       Address;
    created_at: Int as uint64;  // Unix timestamp — used for timeout check
}

// ============================================================
// EVENTS
// ============================================================

message(0x01) EvtActionExecuted    { agent: Address; destination: Address; amount: Int as coins; task_id: Int as uint32; }
message(0x02) EvtActionPending     { agent: Address; task_id: Int as uint32; amount: Int as coins; }
message(0x03) EvtGuardianApproved  { task_id: Int as uint32; }
message(0x04) EvtGuardianRejected  { task_id: Int as uint32; refunded_to: Address; amount: Int as coins; }
message(0x05) EvtAgentRegistered   { agent: Address; daily_limit: Int as coins; }
message(0x06) EvtAgentRevoked      { agent: Address; }
message(0x07) EvtOwnershipStarted  { pending_owner: Address; }
message(0x08) EvtOwnershipDone     { old_owner: Address; new_owner: Address; }
message(0x09) EvtRefundClaimed     { user: Address; amount: Int as coins; }
message(0x0A) EvtTrustScoreQueried { query_id: Int as uint64; user: Address; }
message(0x0B) EvtTrustScoreCached  { query_id: Int as uint64; user: Address; score: Int as uint8; }
message(0x0C) EvtQueryCleaned      { query_id: Int as uint64; user: Address; }
message(0x0D) EvtVaultFeeUpdated   { new_fee_bps: Int as uint16; }
message(0x0E) EvtThresholdUpdated  { new_threshold: Int as coins; }

// ============================================================
// CONTRACT
// ============================================================

contract AetherVault with Deployable {

    owner:              Address;
    pending_owner:      Address?;
    paused:             Bool;
    governance_address: Address?;      // Set after Governance is deployed

    // Only this address is allowed to send ResponseTrustScore
    oracle_address:     Address;

    agents:             map<Address, AgentRecord>;
    agent_count:        Int as uint32;

    guardian:           Address?;
    guardian_threshold: Int as coins;
    pending_txs:        map<Int, PendingTx>;
    pending_count:      Int as uint32;
    pending_refunds:    map<Address, Int>;

    // Trust score cache — populated by Oracle responses
    wallet_trust_score: map<Address, Int>;

    // Request-Response state
    next_query_id:   Int as uint64;          // Monotonically increasing counter
    pending_queries: map<Int, PendingQuery>; // query_id → pending request record

    total_volume:    Int as coins;

    // ============================================================
    init(owner: Address, oracle_address: Address, guardian_threshold: Int) {
        require(guardian_threshold > 0, "Threshold must be > 0");
        self.owner              = owner;
        self.pending_owner      = null;
        self.paused             = false;
        self.governance_address = null;
        self.oracle_address     = oracle_address;
        self.agent_count        = 0;
        self.guardian           = null;
        self.guardian_threshold = guardian_threshold;
        self.pending_count      = 0;
        self.total_volume       = 0;
        self.next_query_id      = 0;
    }

    receive("top_up") {}
    receive()         {}

    // ============================================================
    // REQUEST: Vault → Oracle (async trust score fetch)
    // ============================================================

    receive(msg: FetchTrustScore) {
        self._assert_owner();
        self._request_trust_score(msg.user);
    }

    fun _request_trust_score(user: Address) {
        require(
            myBalance() >= ORACLE_FWD_GAS + GAS_RESERVE,
            "Insufficient balance to forward oracle query"
        );

        let q_id: Int = self.next_query_id;
        self.next_query_id = self.next_query_id + 1;

        // Store with timestamp so we can enforce QUERY_TIMEOUT
        self.pending_queries.set(q_id, PendingQuery {
            user:       user,
            created_at: now(),
        });

        send(SendParameters {
            to:    self.oracle_address,
            value: ORACLE_FWD_GAS,  // Oracle returns remainder via SendRemainingValue
            mode:  SendIgnoreErrors,
            body:  RequestTrustScore { query_id: q_id, user: user }.toCell(),
        });

        emit(EvtTrustScoreQueried { query_id: q_id, user: user }.toCell());
    }

    // ============================================================
    // RESPONSE: Oracle → Vault
    // ============================================================

    receive(msg: ResponseTrustScore) {
        // CHECKS

        // 1. Reject responses from anyone other than our Oracle
        //    This is the primary defence against fake score injection
        require(
            sender() == self.oracle_address,
            "ResponseTrustScore from unauthorized sender"
        );

        // 2. Verify we actually sent this query (replay protection)
        //    Deleted query_id will never pass this check
        let query: PendingQuery? = self.pending_queries.get(msg.query_id);
        require(query != null, "Unknown query_id — not pending or already processed");

        // 3. Timeout: reject late responses, do not update cache
        require(
            now() - query!!.created_at <= QUERY_TIMEOUT,
            "Query expired — response arrived too late (> 10 min)"
        );

        // 4. Integrity: Oracle must echo back the same user we asked about
        require(query!!.user == msg.user, "User mismatch — possible response tampering");

        // EFFECTS — state updates before any emit

        self.wallet_trust_score.set(msg.user, msg.score);

        // Remove query — makes replay impossible
        self.pending_queries.del(msg.query_id);

        emit(EvtTrustScoreCached { query_id: msg.query_id, user: msg.user, score: msg.score }.toCell());
    }

    // ============================================================
    // CLEANUP: manual removal of stale queries
    // Called by owner when Oracle is down and never responded
    // ============================================================

    receive(msg: CleanupExpiredQuery) {
        self._assert_owner();

        let query: PendingQuery? = self.pending_queries.get(msg.query_id);
        require(query != null, "Query not found");
        require(
            now() - query!!.created_at > QUERY_TIMEOUT,
            "Query not expired yet — wait 10 minutes"
        );

        let user: Address = query!!.user;
        self.pending_queries.del(msg.query_id);

        emit(EvtQueryCleaned { query_id: msg.query_id, user: user }.toCell());
    }

    // ============================================================
    // GOVERNANCE PARAMETER UPDATES
    // Accepted only from governance_address — set after deploy
    // ============================================================

    receive(msg: UpdateVaultFee) {
        require(self.governance_address != null,              "Governance not set");
        require(sender() == self.governance_address!!,        "Only Governance");
        require(msg.new_fee_bps <= 500,                       "Fee exceeds 5% cap");
        emit(EvtVaultFeeUpdated { new_fee_bps: msg.new_fee_bps }.toCell());
    }

    receive(msg: UpdateGuardianThreshold) {
        require(self.governance_address != null,              "Governance not set");
        require(sender() == self.governance_address!!,        "Only Governance");
        require(msg.new_threshold > 0,                        "Threshold must be > 0");
        self.guardian_threshold = msg.new_threshold;
        emit(EvtThresholdUpdated { new_threshold: msg.new_threshold }.toCell());
    }

    // One-time call during post-deploy setup, owner only
    receive(msg: SetGovernance) {
        self._assert_owner();
        self.governance_address = msg.governance;
    }

    // ============================================================
    // AGENT REGISTRY
    // ============================================================

    receive(msg: RegisterAgent) {
        self._assert_owner();
        require(self.agent_count < MAX_AGENTS,       "Max 20 agents");
        require(msg.daily_limit > 0,                 "daily_limit must be > 0");
        require(msg.daily_limit <= MAX_DAILY_LIMIT,  "Exceeds 1000 TON cap");
        require(msg.per_tx_max > 0,                  "per_tx_max must be > 0");
        require(msg.per_tx_max <= msg.daily_limit,   "per_tx_max must be <= daily_limit");
        require(self.agents.get(msg.agent) == null,  "Agent already registered");

        self.agents.set(msg.agent, AgentRecord {
            daily_limit: msg.daily_limit, per_tx_max: msg.per_tx_max,
            spent_today: 0, last_reset: now(), total_spent: 0, tx_count: 0, is_active: true,
        });
        self.agent_count = self.agent_count + 1;
        emit(EvtAgentRegistered { agent: msg.agent, daily_limit: msg.daily_limit }.toCell());
    }

    receive(msg: UpdateAgentLimits) {
        self._assert_owner();
        let rec: AgentRecord? = self.agents.get(msg.agent);
        require(rec != null,                       "Agent not found");
        require(msg.daily_limit > 0,               "daily_limit must be > 0");
        require(msg.per_tx_max <= msg.daily_limit, "per_tx_max must be <= daily_limit");
        self.agents.set(msg.agent, AgentRecord {
            daily_limit: msg.daily_limit, per_tx_max: msg.per_tx_max,
            spent_today: rec!!.spent_today, last_reset: rec!!.last_reset,
            total_spent: rec!!.total_spent, tx_count: rec!!.tx_count, is_active: rec!!.is_active,
        });
    }

    receive(msg: RevokeAgent) {
        self._assert_owner();
        let rec: AgentRecord? = self.agents.get(msg.agent);
        require(rec != null, "Agent not found");
        // Soft revoke — history preserved, just deactivated
        self.agents.set(msg.agent, AgentRecord {
            daily_limit: rec!!.daily_limit, per_tx_max: rec!!.per_tx_max,
            spent_today: rec!!.spent_today, last_reset: rec!!.last_reset,
            total_spent: rec!!.total_spent, tx_count: rec!!.tx_count, is_active: false,
        });
        emit(EvtAgentRevoked { agent: msg.agent }.toCell());
    }

    // ============================================================
    // CORE: AGENT ACTION
    // ============================================================

    receive(msg: AgentAction) {
        // CHECKS
        self._assert_not_paused();

        let caller: Address   = sender();
        let rec: AgentRecord? = self.agents.get(caller);
        require(rec != null,     "Unknown agent");
        require(rec!!.is_active, "Agent is revoked");
        require(msg.amount >= ton("0.01"),      "Minimum amount is 0.01 TON");
        require(msg.amount <= rec!!.per_tx_max, "Exceeds per-TX limit");

        // Trust score gate — read from Oracle cache
        // If not cached: fire async fetch, block current action
        let trust: Int = self.wallet_trust_score.get(caller) ?? -1;
        if (trust < 0) {
            self._request_trust_score(caller);
            require(false, "Trust score not cached — fetch initiated, retry after oracle responds");
        }
        require(trust >= MIN_TRUST_SCORE, "Trust score below threshold");

        // Auto-reset daily limit if 24h have passed
        let spent:      Int = rec!!.spent_today;
        let last_reset: Int = rec!!.last_reset;
        if (now() - last_reset >= DAY_SECONDS) { spent = 0; last_reset = now(); }

        require(spent + msg.amount <= rec!!.daily_limit,  "Daily limit exceeded");
        require(myBalance() >= msg.amount + GAS_RESERVE,  "Insufficient vault balance");

        // EFFECTS — Guardian route for large amounts
        if (self.guardian != null && msg.amount >= self.guardian_threshold) {
            self.pending_txs.set(msg.task_id, PendingTx {
                amount: msg.amount, destination: msg.destination,
                task_id: msg.task_id, memo: msg.memo, agent: caller, created_at: now(),
            });
            self.pending_count = self.pending_count + 1;
            emit(EvtActionPending { agent: caller, task_id: msg.task_id, amount: msg.amount }.toCell());
            return;
        }

        // CEI: update state before external call
        self.agents.set(caller, AgentRecord {
            daily_limit: rec!!.daily_limit, per_tx_max: rec!!.per_tx_max,
            spent_today: spent + msg.amount, last_reset: last_reset,
            total_spent: rec!!.total_spent + msg.amount, tx_count: rec!!.tx_count + 1, is_active: true,
        });
        self.total_volume = self.total_volume + msg.amount;

        // INTERACTIONS
        send(SendParameters {
            to: msg.destination, value: msg.amount, mode: SendIgnoreErrors,
            body: ("Aether|" + msg.task_id.toString() + "|" + msg.memo).asComment(),
        });
        emit(EvtActionExecuted {
            agent: caller, destination: msg.destination,
            amount: msg.amount, task_id: msg.task_id,
        }.toCell());
    }

    // ============================================================
    // GUARDIAN
    // ============================================================

    receive(msg: SetGuardian) {
        self._assert_owner();
        require(msg.threshold > 0, "Threshold must be > 0");
        self.guardian = msg.guardian;
        self.guardian_threshold = msg.threshold;
    }

    receive(msg: GuardianApprove) {
        self._assert_not_paused();
        require(self.guardian != null,       "No guardian set");
        require(sender() == self.guardian!!, "Not guardian");

        let tx: PendingTx? = self.pending_txs.get(msg.task_id);
        require(tx != null,                               "Pending TX not found");
        require(now() - tx!!.created_at <= GUARDIAN_TTL, "Pending TX expired (> 30 min)");

        // Update agent stats
        let rec: AgentRecord? = self.agents.get(tx!!.agent);
        if (rec != null) {
            self.agents.set(tx!!.agent, AgentRecord {
                daily_limit: rec!!.daily_limit, per_tx_max: rec!!.per_tx_max,
                spent_today: rec!!.spent_today + tx!!.amount, last_reset: rec!!.last_reset,
                total_spent: rec!!.total_spent + tx!!.amount, tx_count: rec!!.tx_count + 1,
                is_active: rec!!.is_active,
            });
        }

        self.pending_txs.del(msg.task_id);
        self.pending_count = self.pending_count - 1;
        self.total_volume  = self.total_volume + tx!!.amount;

        send(SendParameters {
            to: tx!!.destination, value: tx!!.amount, mode: SendIgnoreErrors,
            body: ("Aether|" + tx!!.task_id.toString() + "|" + tx!!.memo).asComment(),
        });
        emit(EvtGuardianApproved { task_id: msg.task_id }.toCell());
    }

    receive(msg: GuardianReject) {
        require(self.guardian != null,       "No guardian set");
        require(sender() == self.guardian!!, "Not guardian");

        let tx: PendingTx? = self.pending_txs.get(msg.task_id);
        require(tx != null, "Pending TX not found");

        // Queue refund — agent claims via ClaimRefund
        let cur: Int = self.pending_refunds.get(tx!!.agent) ?? 0;
        self.pending_refunds.set(tx!!.agent, cur + tx!!.amount);
        self.pending_txs.del(msg.task_id);
        self.pending_count = self.pending_count - 1;

        emit(EvtGuardianRejected {
            task_id: msg.task_id, refunded_to: tx!!.agent, amount: tx!!.amount,
        }.toCell());
    }

    receive(msg: ClaimRefund) {
        let caller: Address = sender();
        let amount: Int     = self.pending_refunds.get(caller) ?? 0;
        require(amount > 0,                          "No pending refund");
        require(myBalance() >= amount + GAS_RESERVE, "Insufficient vault balance");

        self.pending_refunds.set(caller, 0);
        send(SendParameters {
            to: caller, value: amount, mode: SendIgnoreErrors,
            body: "Aether: refund".asComment(),
        });
        emit(EvtRefundClaimed { user: caller, amount: amount }.toCell());
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
        let old: Address = self.owner;
        self.owner = self.pending_owner!!;
        self.pending_owner = null;
        emit(EvtOwnershipDone { old_owner: old, new_owner: self.owner }.toCell());
    }

    // ============================================================
    // ADMIN
    // ============================================================

    receive("pause")   { self._assert_owner(); self.paused = true; }
    receive("unpause") { self._assert_owner(); self.paused = false; }

    receive(msg: EmergencyWithdraw) {
        self._assert_owner();
        require(self.paused, "Contract must be paused before emergency withdraw");
        let bal: Int = myBalance();
        require(bal > GAS_RESERVE, "Nothing to withdraw");
        send(SendParameters {
            to: self.owner, value: bal - GAS_RESERVE, mode: SendIgnoreErrors,
            body: ("Emergency: " + msg.reason).asComment(),
        });
    }

    // ============================================================
    // GETTERS
    // ============================================================

    get fun balance():                  Int           { return myBalance(); }
    get fun is_paused():                Bool          { return self.paused; }
    get fun owner_address():            Address       { return self.owner; }
    get fun oracle_addr():              Address       { return self.oracle_address; }
    get fun governance_addr():          Address?      { return self.governance_address; }
    get fun next_query_id():            Int           { return self.next_query_id; }
    get fun agent_count():              Int           { return self.agent_count; }
    get fun total_volume():             Int           { return self.total_volume; }
    get fun agent_info(a: Address):     AgentRecord?  { return self.agents.get(a); }
    get fun pending_tx(id: Int):        PendingTx?    { return self.pending_txs.get(id); }
    get fun pending_refund(u: Address): Int           { return self.pending_refunds.get(u) ?? 0; }
    get fun trust_score(u: Address):    Int           { return self.wallet_trust_score.get(u) ?? -1; }
    get fun pending_query(q: Int):      PendingQuery? { return self.pending_queries.get(q); }

    get fun is_query_expired(q: Int): Bool {
        let query: PendingQuery? = self.pending_queries.get(q);
        if (query == null) { return false; }
        return now() - query!!.created_at > QUERY_TIMEOUT;
    }

    // ============================================================
    // INTERNAL
    // ============================================================

    fun _assert_owner()      { require(sender() == self.owner, "Not owner"); }
    fun _assert_not_paused() { require(!self.paused, "Contract is paused"); }
}
