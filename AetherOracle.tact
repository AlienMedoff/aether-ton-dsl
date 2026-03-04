// ============================================================
// AetherOracle.tact — Contract 2/3: Oracle + Multisig + Staking
//
// Responsibilities:
//   ✅ Ed25519 k-of-N signature verification — O(1) lookup (no loop bug)
//   ✅ Dual oracle registry: address → pub_key (bidirectional, O(1))
//   ✅ Sequential per-user nonces (replay protection)
//   ✅ Vault whitelist — only registered Vaults can query scores
//   ✅ Request-Response server: answers RequestTrustScore from Vault
//   ✅ Stake-to-Play barrier (5 TON minimum)
//   ✅ Trust Score system (0–100), set by oracles
//   ✅ Result oracle with 1h cooldown (anti-spam)
//   ✅ 24h unstake lockup after last trade
//   ✅ Sentinel emergency pause (independent of owner)
//   ✅ Storm Trade vault forwarding via op 0x7361
//   ✅ Platform fee with hard 5% cap
//   ✅ Governance parameter updates (UpdateOracleMinSigs, UpdateOracleFee)
// ============================================================

import "@stdlib/deploy";

// ============================================================
// CONSTANTS
// ============================================================

const GAS_RESERVE:       Int = ton("0.05");
const MIN_REQUIRED_SIGS: Int = 2;     // Minimum oracle quorum
const SIGNAL_EXPIRY:     Int = 30;    // Seconds before a signal is considered stale
const MIN_MARGIN:        Int = ton("0.1");
const MIN_STAKE:         Int = ton("5");
const MIN_TRUST_SCORE:   Int = 40;
const RESULT_COOLDOWN:   Int = 3600;  // 1 hour between result updates per user
const UNSTAKE_LOCKUP:    Int = 86400; // 24h lockup after last trade
const MAX_FEE_BPS:       Int = 500;   // 5% hard cap

// ============================================================
// SHARED MESSAGES — must be identical in AetherVault.tact
// ============================================================

message RequestTrustScore  { query_id: Int as uint64; user: Address; }
message ResponseTrustScore { query_id: Int as uint64; user: Address; score: Int as uint8; }

// ============================================================
// ORACLE MESSAGES
// ============================================================

message ExecuteSignal {
    pair_id:          Int as uint32;
    is_long:          Bool;
    leverage:         Int as uint32;
    signal_timestamp: Int as uint64;
    nonce:            Int as uint64;
    // Linked list of cells: [oracle_address(267b) | sig_hi(256b) | sig_lo(256b)] × N
    // Each cell optionally has a ref to the next cell in the chain
    signatures:       Cell;
}

message AddOracle                { oracle: Address; pub_key: Int as uint256; }
message RemoveOracle             { oracle: Address; }
message SetTrustScore            { user: Address; score: Int as uint8; }
message UpdateResult             { user: Address; is_win: Bool; pnl: Int as int64; }
message Stake                    {}
message Unstake                  { amount: Int as coins; }
message AddSentinel              { sentinel: Address; }
message RemoveSentinel           { sentinel: Address; }
message TriggerSentinelPause     {}
message AddVaultToWhitelist      { vault: Address; }
message RemoveVaultFromWhitelist { vault: Address; }
message SetGovernance            { governance: Address; }

// Governance-only parameter updates — sender must be governance_address
message UpdateOracleMinSigs { new_min: Int as uint8; }
message UpdateOracleFee     { new_fee_bps: Int as uint16; }

// ============================================================
// STRUCTS
// ============================================================

struct UserStats {
    total_signals:        Int as uint64;
    total_volume:         Int as coins;
    wins:                 Int as uint32;
    losses:               Int as uint32;
    cumulative_pnl:       Int as int64;
    last_trade_timestamp: Int as uint64;
}

// ============================================================
// EVENTS
// ============================================================

message(0x10) EvtPositionOpened  { user: Address; pair_id: Int as uint32; margin: Int as coins; nonce: Int as uint64; }
message(0x11) EvtStaked          { user: Address; amount: Int as coins; }
message(0x12) EvtUnstaked        { user: Address; amount: Int as coins; }
message(0x13) EvtTrustScoreSet   { user: Address; score: Int as uint8; }
message(0x14) EvtResultUpdated   { user: Address; oracle: Address; is_win: Bool; pnl: Int as int64; }
message(0x15) EvtOracleAdded     { oracle: Address; }
message(0x16) EvtOracleRemoved   { oracle: Address; }
message(0x17) EvtEmergencyPause  { triggered_by: Address; }
message(0x18) EvtTrustQueried    { query_id: Int as uint64; vault: Address; user: Address; score: Int as uint8; }
message(0x19) EvtMinSigsUpdated  { new_min: Int as uint8; }
message(0x1A) EvtOracleFeeUpdated { new_fee_bps: Int as uint16; }

// ============================================================
// CONTRACT
// ============================================================

contract AetherOracle with Deployable {

    owner:              Address;
    storm_vault:        Address;  // Storm Trade vault for signal forwarding
    fee_bps:            Int as uint16;
    paused:             Bool;
    governance_address: Address?;

    // Oracle registry — bidirectional for O(1) lookup in both directions
    oracle_pub_keys:     map<Address, Int>;   // address → Ed25519 pub key
    oracle_active:       map<Address, Bool>;  // address → active flag
    active_oracle_count: Int as uint8;
    min_signatures:      Int as uint8;

    sentinels: map<Address, Bool>;

    // Whitelist of Vault contracts allowed to request trust scores
    // Prevents spam and unauthorized cross-contract queries
    vault_whitelist: map<Address, Bool>;

    // User state — split into separate maps for storage efficiency
    // Hot path (ExecuteSignal) only reads nonces, staked, trust score
    // Stats are cold path — read only for analytics
    user_nonces:        map<Address, Int>;
    staked_amount:      map<Address, Int>;
    last_trade_ts:      map<Address, Int>;
    wallet_trust_score: map<Address, Int>;
    last_result_update: map<Address, Int>;
    user_stats:         map<Address, UserStats>;

    // ============================================================
    init(owner: Address, storm_vault: Address, fee_bps: Int) {
        require(fee_bps <= MAX_FEE_BPS, "Fee exceeds 5% cap");
        self.owner               = owner;
        self.storm_vault         = storm_vault;
        self.fee_bps             = fee_bps;
        self.paused              = false;
        self.active_oracle_count = 0;
        self.min_signatures      = MIN_REQUIRED_SIGS;
    }

    // ============================================================
    // REQUEST-RESPONSE: Oracle as server
    // ============================================================

    receive(msg: RequestTrustScore) {
        let vault: Address = sender();

        // Only whitelisted Vault contracts can request scores
        // Protects against spam and unauthorized contract queries
        require(
            self.vault_whitelist.get(vault) == true,
            "Vault not in whitelist — unauthorized query"
        );

        let score: Int = self.wallet_trust_score.get(msg.user) ?? 0;

        // Reply to sender (the Vault) — SendRemainingValue returns unused gas
        // Vault pays for the full round-trip with ORACLE_FWD_GAS
        send(SendParameters {
            to:    vault,
            value: 0,
            mode:  SendRemainingValue,
            body:  ResponseTrustScore {
                query_id: msg.query_id,
                user:     msg.user,
                score:    score,
            }.toCell(),
        });

        emit(EvtTrustQueried {
            query_id: msg.query_id, vault: vault, user: msg.user, score: score,
        }.toCell());
    }

    // ============================================================
    // VAULT WHITELIST
    // ============================================================

    receive(msg: AddVaultToWhitelist) {
        self._assert_owner();
        self.vault_whitelist.set(msg.vault, true);
    }

    receive(msg: RemoveVaultFromWhitelist) {
        self._assert_owner();
        require(self.vault_whitelist.get(msg.vault) == true, "Not in whitelist");
        self.vault_whitelist.set(msg.vault, false);
    }

    // ============================================================
    // GOVERNANCE PARAMETER UPDATES
    // ============================================================

    receive(msg: UpdateOracleMinSigs) {
        require(self.governance_address != null,       "Governance not set");
        require(sender() == self.governance_address!!, "Only Governance");
        require(msg.new_min >= 2,                      "min_sigs must be >= 2");
        require(msg.new_min <= self.active_oracle_count, "Exceeds active oracle count");
        self.min_signatures = msg.new_min;
        emit(EvtMinSigsUpdated { new_min: msg.new_min }.toCell());
    }

    receive(msg: UpdateOracleFee) {
        require(self.governance_address != null,       "Governance not set");
        require(sender() == self.governance_address!!, "Only Governance");
        require(msg.new_fee_bps <= MAX_FEE_BPS,        "Fee exceeds 5% cap");
        self.fee_bps = msg.new_fee_bps;
        emit(EvtOracleFeeUpdated { new_fee_bps: msg.new_fee_bps }.toCell());
    }

    receive(msg: SetGovernance) {
        self._assert_owner();
        self.governance_address = msg.governance;
    }

    // ============================================================
    // ORACLE MANAGEMENT (owner only)
    // ============================================================

    receive(msg: AddOracle) {
        self._assert_owner();
        require(self.oracle_active.get(msg.oracle) != true, "Oracle already registered");
        require(self.active_oracle_count < 20,              "Max 20 oracles");

        self.oracle_pub_keys.set(msg.oracle, msg.pub_key);
        self.oracle_active.set(msg.oracle, true);
        self.active_oracle_count = self.active_oracle_count + 1;

        emit(EvtOracleAdded { oracle: msg.oracle }.toCell());
    }

    receive(msg: RemoveOracle) {
        self._assert_owner();
        require(self.oracle_active.get(msg.oracle) == true, "Not an active oracle");
        require(
            self.active_oracle_count - 1 >= self.min_signatures,
            "Cannot remove: would break quorum"
        );

        self.oracle_pub_keys.del(msg.oracle);
        self.oracle_active.set(msg.oracle, false);
        self.active_oracle_count = self.active_oracle_count - 1;

        emit(EvtOracleRemoved { oracle: msg.oracle }.toCell());
    }

    // ============================================================
    // TRUST SCORE & RESULTS (oracle signers only)
    // ============================================================

    receive(msg: SetTrustScore) {
        self._assert_oracle();
        require(msg.score <= 100, "Score must be 0–100");
        self.wallet_trust_score.set(msg.user, msg.score);
        emit(EvtTrustScoreSet { user: msg.user, score: msg.score }.toCell());
    }

    receive(msg: UpdateResult) {
        self._assert_oracle();
        let last: Int = self.last_result_update.get(msg.user) ?? 0;
        require(now() >= last + RESULT_COOLDOWN, "Result cooldown: wait 1 hour");

        self.last_result_update.set(msg.user, now());

        let s: UserStats = self.user_stats.get(msg.user) ?? UserStats {
            total_signals: 0, total_volume: 0, wins: 0,
            losses: 0, cumulative_pnl: 0, last_trade_timestamp: 0,
        };
        self.user_stats.set(msg.user, UserStats {
            total_signals:        s.total_signals,
            total_volume:         s.total_volume,
            wins:                 msg.is_win ? s.wins + 1 : s.wins,
            losses:               msg.is_win ? s.losses : s.losses + 1,
            cumulative_pnl:       s.cumulative_pnl + msg.pnl,
            last_trade_timestamp: now(),
        });

        emit(EvtResultUpdated {
            user: msg.user, oracle: sender(), is_win: msg.is_win, pnl: msg.pnl,
        }.toCell());
    }

    // ============================================================
    // STAKE-TO-PLAY
    // ============================================================

    receive(msg: Stake) {
        let amount: Int = context().value;
        require(amount > 0, "Zero stake");
        let cur: Int = self.staked_amount.get(sender()) ?? 0;
        self.staked_amount.set(sender(), cur + amount);
        emit(EvtStaked { user: sender(), amount: amount }.toCell());
    }

    receive(msg: Unstake) {
        let caller: Address = sender();
        let staked: Int     = self.staked_amount.get(caller) ?? 0;
        require(staked >= msg.amount,                                     "Insufficient staked balance");
        require(now() >= (self.last_trade_ts.get(caller) ?? 0) + UNSTAKE_LOCKUP, "Unstake lockup: 24h after last trade");
        require(myBalance() >= msg.amount + GAS_RESERVE,                  "Insufficient contract balance");

        // CEI: update state before send
        self.staked_amount.set(caller, staked - msg.amount);

        send(SendParameters {
            to: caller, value: msg.amount, mode: SendIgnoreErrors,
            body: "Aether: unstake".asComment(),
        });
        emit(EvtUnstaked { user: caller, amount: msg.amount }.toCell());
    }

    // ============================================================
    // SENTINEL — independent emergency circuit breaker
    // Sentinel key should be stored separately from oracle keys
    // ============================================================

    receive(msg: AddSentinel) {
        self._assert_owner();
        self.sentinels.set(msg.sentinel, true);
    }

    receive(msg: RemoveSentinel) {
        self._assert_owner();
        require(self.sentinels.get(msg.sentinel) == true, "Not a sentinel");
        self.sentinels.set(msg.sentinel, false);
    }

    receive(msg: TriggerSentinelPause) {
        let caller: Address = sender();
        require(
            self.sentinels.get(caller) == true || caller == self.owner,
            "Not a sentinel or owner"
        );
        self.paused = true;
        emit(EvtEmergencyPause { triggered_by: caller }.toCell());
    }

    // ============================================================
    // EXECUTE SIGNAL — DeFi hot-path
    // ============================================================

    receive(msg: ExecuteSignal) {
        // CHECKS
        require(!self.paused, "Contract is paused");

        let caller: Address = sender();
        let ts:     Int     = now();

        // Signal freshness — prevents replaying old signals
        require(ts <= msg.signal_timestamp + SIGNAL_EXPIRY, "Signal expired (> 30 seconds)");

        // Sequential nonce — prevents replay of exact same message
        let cur_nonce: Int = self.user_nonces.get(caller) ?? 0;
        require(msg.nonce == cur_nonce + 1, "Invalid nonce — must be sequential");

        // Anti-bot gates
        require((self.staked_amount.get(caller) ?? 0) >= MIN_STAKE,            "Minimum stake: 5 TON");
        require((self.wallet_trust_score.get(caller) ?? 0) >= MIN_TRUST_SCORE, "Trust score below 40");

        let total_value:  Int = context().value;
        let platform_fee: Int = total_value * self.fee_bps / 10000;
        let margin:       Int = total_value - platform_fee;
        require(margin >= MIN_MARGIN, "Margin below minimum (0.1 TON)");

        // Ed25519 k-of-N multisig verification
        require(
            self._verify_multi_sig(
                msg.pair_id, msg.is_long, msg.leverage,
                msg.signal_timestamp, msg.nonce, caller, msg.signatures
            ),
            "Oracle quorum not reached"
        );

        // CEI: update state before external calls
        self.user_nonces.set(caller, msg.nonce);
        self.last_trade_ts.set(caller, ts);

        let s: UserStats = self.user_stats.get(caller) ?? UserStats {
            total_signals: 0, total_volume: 0, wins: 0,
            losses: 0, cumulative_pnl: 0, last_trade_timestamp: 0,
        };
        self.user_stats.set(caller, UserStats {
            total_signals:        s.total_signals + 1,
            total_volume:         s.total_volume + margin,
            wins: s.wins, losses: s.losses, cumulative_pnl: s.cumulative_pnl,
            last_trade_timestamp: ts,
        });

        // INTERACTIONS
        if (platform_fee > 0) {
            send(SendParameters {
                to: self.owner, value: platform_fee, mode: SendIgnoreErrors,
                body: "Aether: platform fee".asComment(),
            });
        }

        // Forward position to Storm Trade vault
        send(SendParameters {
            to:    self.storm_vault,
            value: margin,
            mode:  SendIgnoreErrors,
            body:  beginCell()
                       .storeUint(0x7361, 16)
                       .storeAddress(caller)
                       .storeUint(msg.pair_id, 32)
                       .storeBool(msg.is_long)
                       .storeUint(msg.leverage, 32)
                       .storeCoins(margin)
                   .endCell(),
        });

        emit(EvtPositionOpened {
            user: caller, pair_id: msg.pair_id, margin: margin, nonce: msg.nonce,
        }.toCell());
    }

    // ============================================================
    // GETTERS
    // ============================================================

    get fun is_paused():             Bool  { return self.paused; }
    get fun oracle_count():          Int   { return self.active_oracle_count; }
    get fun min_sigs():              Int   { return self.min_signatures; }
    get fun fee_bps():               Int   { return self.fee_bps; }
    get fun staked(u: Address):      Int   { return self.staked_amount.get(u) ?? 0; }
    get fun trust_score(u: Address): Int   { return self.wallet_trust_score.get(u) ?? 0; }
    get fun next_nonce(u: Address):  Int   { return (self.user_nonces.get(u) ?? 0) + 1; }
    get fun is_vault(v: Address):    Bool  { return self.vault_whitelist.get(v) == true; }
    get fun is_oracle(a: Address):   Bool  { return self.oracle_active.get(a) == true; }
    get fun oracle_pub_key(a: Address): Int? { return self.oracle_pub_keys.get(a); }

    get fun is_eligible(u: Address): Bool {
        return (self.staked_amount.get(u) ?? 0) >= MIN_STAKE
            && (self.wallet_trust_score.get(u) ?? 0) >= MIN_TRUST_SCORE;
    }

    // ============================================================
    // INTERNAL: Ed25519 k-of-N multisig verification
    //
    // Fix vs naive implementations:
    //   - No newAddress(0, pub_key) bug — TON address != raw pub_key
    //   - O(1) lookup: oracle_address → pub_key via map (no loop over all oracles)
    //   - Deduplication via seen_keys map (prevents double-counting same key)
    //   - Linked cell list allows arbitrary number of signatures
    //
    // Signature cell format (each cell in the chain):
    //   oracle_address: 267 bits
    //   sig_hi:         256 bits
    //   sig_lo:         256 bits
    //   = 779 bits total per signature block
    //   optional ref → next cell in chain
    // ============================================================

    fun _verify_multi_sig(
        pair_id:   Int,
        is_long:   Bool,
        leverage:  Int,
        timestamp: Int,
        nonce:     Int,
        user:      Address,
        sigs_cell: Cell,
    ): Bool {
        // Deterministic message hash — same as what oracles sign off-chain
        let msg_hash: Int = beginCell()
            .storeAddress(user)
            .storeUint(pair_id, 32)
            .storeBool(is_long)
            .storeUint(leverage, 32)
            .storeUint(timestamp, 64)
            .storeUint(nonce, 64)
        .endCell().hash();

        let valid_count: Int            = 0;
        let seen:        map<Int, Bool> = emptyMap(); // Dedup by pub_key
        let cur:         Cell?          = sigs_cell;

        while (cur != null && valid_count < self.min_signatures) {
            let s: Slice = cur!!.beginParse();
            if (s.remainingBits() < 779) { break; } // Malformed cell — skip

            let oracle_addr: Address = s.loadAddress();
            let sig_hi:      Int     = s.loadUint(256);
            let sig_lo:      Int     = s.loadUint(256);

            // O(1) lookup — no iteration over all oracles
            let pub_key: Int? = self.oracle_pub_keys.get(oracle_addr);

            if (pub_key != null && self.oracle_active.get(oracle_addr) == true) {
                // Dedup by pub_key — prevents two addresses sharing same key
                if (seen.get(pub_key!!) != true) {
                    let sig: Int = sig_hi * (1 << 256) + sig_lo;
                    if (checkSignature(msg_hash, sig, pub_key!!)) {
                        seen.set(pub_key!!, true);
                        valid_count = valid_count + 1;
                    }
                }
            }

            // Advance to next cell in linked list
            cur = s.remainingRefs() > 0 ? s.loadRef() : null;
        }

        return valid_count >= self.min_signatures;
    }

    fun _assert_owner()  { require(sender() == self.owner, "Not owner"); }
    fun _assert_oracle() { require(self.oracle_active.get(sender()) == true, "Not a registered oracle"); }
}
