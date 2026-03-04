# 🌌 ton-tx-dsl

Universal Agentic Runtime & Orchestration Layer for Telegram Mini Apps.

## Quick Test in Google Colab

1. Open `notebooks/aether_os_colab.ipynb` in Google Colab
2. **Runtime → Run all**
3. Watch 22 tests pass on Mock data

No Docker, no Redis, no TON API key required for mock testing.

## Project Structure

```
aether_os/
├── common/
│   ├── engine.py              # DAGOrchestrator, Syscalls, Reaper
│   ├── config.py              # ConfigLoader with fail-fast validation
│   ├── ton_service.py         # TON API client (hardened)
│   └── agent_context_manager.py
├── agents/
│   ├── base_agent.py
│   ├── transaction_executor.py
│   └── rollback_agent.py
├── orchestrator/
│   ├── bdd_parser.py          # Gherkin → task steps
│   └── scenario_runner.py     # FSM with rollback
├── contracts/
│   ├── AetherVault.tact       # Core escrow + Guardian 2-key
│   ├── AetherOracle.tact      # Ed25519 multisig + Trust Scores
│   └── AetherGovernance.tact  # 48h Timelock
├── features/
│   └── transactions.feature   # BDD test scenarios
├── tests/
│   ├── test_engine.py         # 27 engine tests
│   ├── test_config.py         # 37 config tests
│   └── governance.spec.ts     # 38 contract tests
├── notebooks/
│   └── aether_os_colab.ipynb  # ← Run this in Colab
├── scripts/
│   └── deploy.ts              # TON contract deployment
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Local Run (Mock mode)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/Aether-TMA-TON-Agent-OS.git
cd Aether-TMA-TON-Agent-OS

# 2. Install
pip install -r requirements.txt

# 3. Configure (Mock — no real keys needed)
cp .env.example .env

# 4. Run tests
pytest tests/test_engine.py tests/test_config.py -v

# 5. Run demo DAG
TON_MODE=MOCK TON_API_KEY=mock TON_API_ENDPOINT=https://testnet.toncenter.com/api/v2 \
AGENT_ID=main python main.py
```

## Docker (full stack)

```bash
cp .env.example .env
# Edit .env — set TON_API_KEY
docker-compose up --build
```

## Smart Contracts (TON)

```bash
npm install
npx jest tests/governance.spec.ts --verbose
npx blueprint run deploy --network testnet
```

## TON Mode Switch

| Mode    | What happens |
|---------|-------------|
| MOCK    | No network calls, in-memory state |
| TESTNET | Real TON testnet, safe testing |
| MAINNET | Real money — double check everything |

Change `TON_MODE` in `.env` or `docker-compose.yml`.
