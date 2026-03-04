// ============================================================
// governance_receivers.patch.tact
//
// This file documents the receivers that must be added to
// AetherVault.tact and AetherOracle.tact so they accept
// parameter updates from AetherGovernance.
//
// Both contracts validate: require(sender() == governance_address)
// This is the only protection against unauthorized param changes.
//
// All message types below are already defined in the main contracts.
// This file serves as a reference / integration checklist.
// ============================================================


// ══════════════════════════════════════════════════════════════
// PART 1: AetherVault.tact — already included in latest version
// ══════════════════════════════════════════════════════════════

// Fields to add to contract state:
//   governance_address: Address?;

// Add to init():
//   self.governance_address = null;

// Receivers to add:

// receive(msg: UpdateVaultFee) {
//     require(self.governance_address != null,       "Governance not set");
//     require(sender() == self.governance_address!!, "Only Governance");
//     require(msg.new_fee_bps <= 500,                "Fee exceeds 5% cap");
//     emit(EvtVaultFeeUpdated { new_fee_bps: msg.new_fee_bps }.toCell());
// }

// receive(msg: UpdateGuardianThreshold) {
//     require(self.governance_address != null,       "Governance not set");
//     require(sender() == self.governance_address!!, "Only Governance");
//     require(msg.new_threshold > 0,                 "Threshold must be > 0");
//     self.guardian_threshold = msg.new_threshold;
//     emit(EvtThresholdUpdated { new_threshold: msg.new_threshold }.toCell());
// }

// One-time setup call from owner after Governance is deployed:
// receive(msg: SetGovernance) {
//     self._assert_owner();
//     self.governance_address = msg.governance;
// }

// Events to add:
// message(0x0D) EvtVaultFeeUpdated  { new_fee_bps: Int as uint16; }
// message(0x0E) EvtThresholdUpdated { new_threshold: Int as coins; }

// Getter to add:
// get fun governance_addr(): Address? { return self.governance_address; }


// ══════════════════════════════════════════════════════════════
// PART 2: AetherOracle.tact — already included in latest version
// ══════════════════════════════════════════════════════════════

// Fields to add to contract state:
//   governance_address: Address?;

// Add to init():
//   self.governance_address = null;

// Receivers to add:

// receive(msg: UpdateOracleMinSigs) {
//     require(self.governance_address != null,         "Governance not set");
//     require(sender() == self.governance_address!!,   "Only Governance");
//     require(msg.new_min >= 2,                        "min_sigs must be >= 2");
//     require(msg.new_min <= self.active_oracle_count, "Exceeds active oracle count");
//     self.min_signatures = msg.new_min;
//     emit(EvtMinSigsUpdated { new_min: msg.new_min }.toCell());
// }

// receive(msg: UpdateOracleFee) {
//     require(self.governance_address != null,       "Governance not set");
//     require(sender() == self.governance_address!!, "Only Governance");
//     require(msg.new_fee_bps <= 500,                "Fee exceeds 5% cap");
//     self.fee_bps = msg.new_fee_bps;
//     emit(EvtOracleFeeUpdated { new_fee_bps: msg.new_fee_bps }.toCell());
// }

// receive(msg: SetGovernance) {
//     self._assert_owner();
//     self.governance_address = msg.governance;
// }

// Events to add:
// message(0x19) EvtMinSigsUpdated   { new_min: Int as uint8; }
// message(0x1A) EvtOracleFeeUpdated { new_fee_bps: Int as uint16; }

// Getter to add:
// get fun governance_addr(): Address? { return self.governance_address; }


// ══════════════════════════════════════════════════════════════
// FULL INTERACTION DIAGRAM
// ══════════════════════════════════════════════════════════════
//
//  Owner
//    │
//    ├──► ProposeAction(type=1, param=100) ──────► Governance
//    │                                                 │
//    │                                         [stored in timelock]
//    │                                         [waits 48 hours]
//    │
//    ├──► ExecuteAction(action_id) ────────────► Governance
//    │                                                 │
//    │                                   [CEI: mark executed first]
//    │                                                 │
//    │                              ┌──────────────────▼──────────────┐
//    │                              │        _dispatch(type=1, 100)    │
//    │                              └──────────────────┬──────────────┘
//    │                                                 │
//    │                              UpdateVaultFee(100) ▼
//    │                                           AetherVault
//    │                                  require(sender == governance) ✅
//    │                                  fee updated
//    │
//    └──► (same flow for Oracle via type=2,6,7,8)
//
//
//  VAULT ◄──────────────────────────────────── ORACLE
//    │                                             │
//    │── RequestTrustScore(query_id=5, user) ─────►│
//    │   value: 0.1 TON (covers round-trip gas)    │
//    │                                             │ O(1) lookup trust_score[user]
//    │◄─ ResponseTrustScore(query_id=5, score) ────│
//    │   mode: SendRemainingValue                  │
//    │                                             │
//    │ checks:                                     │
//    │   sender == oracle_address             ✅   │
//    │   query_id in pending_queries          ✅   │
//    │   now() - created_at <= 10 min         ✅   │
//    │   response.user == query.user          ✅   │
//    │                                             │
//    │ wallet_trust_score[user] = score            │
//    │ pending_queries.del(query_id=5)             │
//
//
//  DEPLOY ORDER:
//    1.  Oracle.deploy(owner, storm_vault, fee_bps)
//    2.  Vault.deploy(owner, oracle.address, guardian_threshold)
//    3.  Governance.deploy(owner, vault.address, oracle.address)
//    4.  Oracle.AddVaultToWhitelist(vault.address)
//    5.  Vault.SetGuardian(guardian, threshold)
//    6.  Oracle.AddOracle(addr1, pubkey1)
//    7.  Oracle.AddOracle(addr2, pubkey2)
//    8.  Vault.SetGovernance(governance.address)    ← Vault accepts Governance commands
//    9.  Oracle.SetGovernance(governance.address)   ← Oracle accepts Governance commands
//    10. Vault.TransferOwnership(governance.address)
//    11. Oracle.TransferOwnership(governance.address)
//    12. [via Governance action] Vault.AcceptOwnership()
//    13. [via Governance action] Oracle.AcceptOwnership()
