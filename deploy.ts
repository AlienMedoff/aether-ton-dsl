// ============================================================
// deploy.ts — Blueprint Deploy Script
// Деплой AetherVault + AetherOracle + AetherGovernance
//
// Порядок деплоя КРИТИЧЕН:
//   1. Деплоим Oracle (не зависит от других)
//   2. Деплоим Vault (нужен oracle_address)
//   3. Деплоим Governance (нужны vault + oracle адреса)
//   4. Пост-деплой: whitelist Vault в Oracle, set governance в Vault/Oracle
//
// Запуск:
//   npx blueprint run deploy --network testnet
// ============================================================

import { toNano, Address, beginCell } from "@ton/core";
import { NetworkProvider, sleep } from "@ton/blueprint";

// Импорт wrapper-классов (генерируются компилятором Tact)
import { AetherVault }      from "../wrappers/AetherVault";
import { AetherOracle }     from "../wrappers/AetherOracle";
import { AetherGovernance } from "../wrappers/AetherGovernance";

// ============================================================
// КОНФИГУРАЦИЯ — заполни перед деплоем
// ============================================================

const CONFIG = {
    // Storm Trade vault адрес (mainnet/testnet)
    STORM_VAULT: Address.parse("EQD..."),   // TODO: реальный адрес Storm Trade

    // Параметры
    INITIAL_FEE_BPS:        50,             // 0.5% platform fee
    GUARDIAN_THRESHOLD:     toNano("5"),    // Суммы >= 5 TON требуют Guardian
    INITIAL_BALANCE_VAULT:  toNano("1"),    // Начальный баланс Vault
    INITIAL_BALANCE_ORACLE: toNano("1"),    // Начальный баланс Oracle
    INITIAL_BALANCE_GOV:    toNano("0.5"), // Начальный баланс Governance

    // Адрес Guardian (второй ключ безопасности)
    GUARDIAN: Address.parse("EQD..."),      // TODO: твой guardian кошелёк

    // Первые оракулы
    ORACLES: [
        {
            address: Address.parse("EQD..."), // TODO: адрес первого оракула
            pub_key: BigInt("0x..."),          // TODO: Ed25519 pub key
        },
        {
            address: Address.parse("EQD..."), // TODO: адрес второго оракула
            pub_key: BigInt("0x..."),
        },
    ],
};

// ============================================================
// DEPLOY FUNCTION
// ============================================================

export async function run(provider: NetworkProvider) {
    const sender = provider.sender();
    const ownerAddress = sender.address!;

    console.log("═══════════════════════════════════════════");
    console.log("  Aether Protocol — Blueprint Deploy");
    console.log("═══════════════════════════════════════════");
    console.log(`  Owner:   ${ownerAddress}`);
    console.log(`  Network: ${provider.network()}`);
    console.log("");

    // ──────────────────────────────────────────────────────────
    // ШАГ 1: Деплой AetherOracle
    // Oracle не зависит ни от кого — деплоим первым
    // ──────────────────────────────────────────────────────────

    console.log("[ 1/5 ] Deploying AetherOracle...");

    const oracle = provider.open(
        await AetherOracle.fromInit(
            ownerAddress,
            CONFIG.STORM_VAULT,
            CONFIG.INITIAL_FEE_BPS,
        )
    );

    await oracle.send(
        sender,
        { value: CONFIG.INITIAL_BALANCE_ORACLE },
        { $$type: "Deploy", queryId: 0n }
    );

    await provider.waitForDeploy(oracle.address);
    console.log(`  ✅ AetherOracle deployed: ${oracle.address}`);

    // ──────────────────────────────────────────────────────────
    // ШАГ 2: Деплой AetherVault
    // Vault нужен адрес Oracle — передаём в init
    // ──────────────────────────────────────────────────────────

    console.log("[ 2/5 ] Deploying AetherVault...");

    const vault = provider.open(
        await AetherVault.fromInit(
            ownerAddress,
            oracle.address,          // oracle_address для Request-Response
            CONFIG.GUARDIAN_THRESHOLD,
        )
    );

    await vault.send(
        sender,
        { value: CONFIG.INITIAL_BALANCE_VAULT },
        { $$type: "Deploy", queryId: 0n }
    );

    await provider.waitForDeploy(vault.address);
    console.log(`  ✅ AetherVault deployed: ${vault.address}`);

    // ──────────────────────────────────────────────────────────
    // ШАГ 3: Деплой AetherGovernance
    // Governance знает адреса Vault и Oracle
    // ──────────────────────────────────────────────────────────

    console.log("[ 3/5 ] Deploying AetherGovernance...");

    const governance = provider.open(
        await AetherGovernance.fromInit(
            ownerAddress,
            vault.address,
            oracle.address,
        )
    );

    await governance.send(
        sender,
        { value: CONFIG.INITIAL_BALANCE_GOV },
        { $$type: "Deploy", queryId: 0n }
    );

    await provider.waitForDeploy(governance.address);
    console.log(`  ✅ AetherGovernance deployed: ${governance.address}`);

    // ──────────────────────────────────────────────────────────
    // ШАГ 4: Пост-деплой конфигурация
    // ──────────────────────────────────────────────────────────

    console.log("[ 4/5 ] Post-deploy configuration...");

    // Небольшая пауза — ждём подтверждения транзакций
    await sleep(3000);

    // 4a. Whitelist Vault в Oracle
    // Только whitelisted Vault может запрашивать trust scores
    console.log("  → Adding Vault to Oracle whitelist...");
    await oracle.send(
        sender,
        { value: toNano("0.05") },
        { $$type: "AddVaultToWhitelist", vault: vault.address }
    );
    await sleep(2000);

    // 4b. Устанавливаем Guardian в Vault
    console.log("  → Setting Guardian in Vault...");
    await vault.send(
        sender,
        { value: toNano("0.05") },
        {
            $$type:     "SetGuardian",
            guardian:   CONFIG.GUARDIAN,
            threshold:  CONFIG.GUARDIAN_THRESHOLD,
        }
    );
    await sleep(2000);

    // 4c. Регистрируем оракулов в Oracle
    console.log("  → Registering oracles...");
    for (const oracleConfig of CONFIG.ORACLES) {
        await oracle.send(
            sender,
            { value: toNano("0.05") },
            {
                $$type:  "AddOracle",
                oracle:  oracleConfig.address,
                pub_key: oracleConfig.pub_key,
            }
        );
        await sleep(2000);
        console.log(`    ✅ Oracle registered: ${oracleConfig.address}`);
    }

    // 4d. Передаём ownership Governance-контракту
    // ВНИМАНИЕ: после этого шага изменения параметров идут только через 48h Timelock
    // Сначала убедись что Governance задеплоен корректно!
    console.log("  → Transferring ownership to Governance...");

    // Vault: инициируем transfer
    await vault.send(
        sender,
        { value: toNano("0.05") },
        { $$type: "TransferOwnership", new_owner: governance.address }
    );
    await sleep(2000);

    // Oracle: инициируем transfer
    await oracle.send(
        sender,
        { value: toNano("0.05") },
        { $$type: "TransferOwnership", new_owner: governance.address }
    );
    await sleep(2000);

    // Governance принимает ownership от имени себя
    // Для этого нужно вызвать AcceptOwnership через Governance.executeAction
    // ИЛИ сделать это вручную если Governance ещё не управляет Vault/Oracle
    // TODO: реализовать через initial governance action если нужен DAO-style

    // ──────────────────────────────────────────────────────────
    // ШАГ 5: Верификация
    // ──────────────────────────────────────────────────────────

    console.log("[ 5/5 ] Verifying deployment...");

    const vaultBalance    = await vault.getBalance();
    const oracleBalance   = await oracle.getBalance();
    const oracleCount     = await oracle.getOracleCount();
    const isPaused        = await vault.getIsPaused();

    console.log("");
    console.log("═══════════════════════════════════════════");
    console.log("  Deployment Summary");
    console.log("═══════════════════════════════════════════");
    console.log(`  AetherVault:      ${vault.address}`);
    console.log(`  AetherOracle:     ${oracle.address}`);
    console.log(`  AetherGovernance: ${governance.address}`);
    console.log("");
    console.log(`  Vault balance:    ${vaultBalance} nTON`);
    console.log(`  Oracle balance:   ${oracleBalance} nTON`);
    console.log(`  Active oracles:   ${oracleCount}`);
    console.log(`  Vault paused:     ${isPaused}`);
    console.log("");
    console.log("  ⚠️  TODO before mainnet:");
    console.log("     1. AcceptOwnership через Governance для Vault и Oracle");
    console.log("     2. Проверить whitelist через oracle.getIsVault()");
    console.log("     3. Задеплоить тест-агента и проверить AgentAction");
    console.log("     4. Протестировать FetchTrustScore → ResponseTrustScore");
    console.log("     5. Протестировать полный Governance flow (ProposeAction → 48h → ExecuteAction)");
    console.log("═══════════════════════════════════════════");

    // Сохраняем адреса в файл для дальнейшего использования
    const deployment = {
        network:    provider.network(),
        deployed_at: new Date().toISOString(),
        contracts: {
            vault:      vault.address.toString(),
            oracle:     oracle.address.toString(),
            governance: governance.address.toString(),
        },
        config: {
            fee_bps:            CONFIG.INITIAL_FEE_BPS,
            guardian_threshold: CONFIG.GUARDIAN_THRESHOLD.toString(),
            guardian:           CONFIG.GUARDIAN.toString(),
        }
    };

    console.log("\n  Deployment JSON (save this!):");
    console.log(JSON.stringify(deployment, null, 2));
}

// ============================================================
// HELPER: Тестовый сценарий для Testnet
// Вызови отдельно после деплоя: npx blueprint run smoke-test
// ============================================================

export async function smokeTest(provider: NetworkProvider) {
    const sender = provider.sender();

    // Загружаем задеплоенные адреса (замени на реальные)
    const vault = provider.open(
        AetherVault.fromAddress(Address.parse("EQD..."))  // TODO
    );
    const oracle = provider.open(
        AetherOracle.fromAddress(Address.parse("EQD...")) // TODO
    );
    const governance = provider.open(
        AetherGovernance.fromAddress(Address.parse("EQD...")) // TODO
    );

    console.log("=== Smoke Test: Request-Response Protocol ===");

    // Тест 1: FetchTrustScore → должен создать pending query
    console.log("Test 1: FetchTrustScore...");
    await vault.send(
        sender,
        { value: toNano("0.2") },    // 0.1 на запрос + 0.1 запас
        { $$type: "FetchTrustScore", user: sender.address! }
    );
    await sleep(5000);

    const queryId   = (await vault.getNextQueryId()) - 1n;
    const queryInfo = await vault.getPendingQuery(queryId);
    console.log(`  query_id: ${queryId}, pending: ${queryInfo !== null}`);

    // Тест 2: Проверяем что скор закэшировался
    await sleep(10000); // ждём ответа Oracle
    const score = await vault.getTrustScore(sender.address!);
    console.log(`  trust_score после ответа Oracle: ${score}`);

    // Тест 3: Governance proposal
    console.log("Test 2: Governance ProposeAction (SetFee = 1%)...");
    await governance.send(
        sender,
        { value: toNano("0.05") },
        {
            $$type:       "ProposeAction",
            action_type:  1n,
            param_int:    100n,        // 1% fee
            description:  "Set vault fee to 1%",
        }
    );
    await sleep(3000);

    const actionCount = await governance.getActionCount();
    console.log(`  Total actions proposed: ${actionCount}`);

    console.log("=== Smoke Test Complete ===");
}
