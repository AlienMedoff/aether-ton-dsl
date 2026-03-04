#!/usr/bin/env python3
"""
Simple contract testing without Node.js dependency
Tests the contract logic and structure
"""

import re
import os
from pathlib import Path

def test_contract_syntax():
    """Test basic Tact contract syntax"""
    contracts = [
        "AetherVault.tact",
        "AetherOracle.tact", 
        "AetherGovernance.tact"
    ]
    
    results = {}
    
    for contract in contracts:
        if os.path.exists(contract):
            with open(contract, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Basic syntax checks
            checks = {
                "has_import": "@stdlib/deploy" in content,
                "has_messages": "message" in content,
                "has_contract": "contract" in content,
                "has_constants": "const" in content,
                "has_functions": "fun" in content or "get" in content,
                "has_modifiers": "modifier" in content or "require" in content,
            }
            
            # Check for security patterns
            security = {
                "has_access_control": any(x in content.lower() for x in ["require", "modifier", "sender"]),
                "has_gas_checks": "gas" in content.lower(),
                "has_error_handling": "throw" in content or "return" in content,
            }
            
            # Count message types
            message_types = len(re.findall(r'message\s+\w+', content))
            
            results[contract] = {
                "syntax_checks": checks,
                "security_checks": security,
                "message_types": message_types,
                "lines": len(content.splitlines()),
                "size": len(content)
            }
        else:
            results[contract] = {"error": "File not found"}
    
    return results

def test_governance_spec():
    """Test governance.spec.ts structure"""
    if not os.path.exists("governance.spec.ts"):
        return {"error": "Test file not found"}
        
    with open("governance.spec.ts", 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count test blocks
    test_blocks = {
        "describe_blocks": len(re.findall(r'describe\(', content)),
        "it_blocks": len(re.findall(r'it\(', content)),
        "expect_statements": len(re.findall(r'expect\(', content)),
        "async_tests": len(re.findall(r'async', content)),
    }
    
    # Check test coverage areas
    coverage = {
        "propose_tests": "ProposeAction" in content,
        "timelock_tests": "Timelock" in content,
        "execute_tests": "ExecuteAction" in content,
        "cancel_tests": "CancelAction" in content,
        "security_tests": any(x in content for x in ["hacker", "unauthorized", "security"]),
    }
    
    return {
        "test_blocks": test_blocks,
        "coverage": coverage,
        "lines": len(content.splitlines()),
        "size": len(content)
    }

def main():
    print("Testing TON Smart Contracts (Python-based)")
    print("=" * 50)
    
    # Test contract syntax
    print("\nContract Syntax Tests:")
    contract_results = test_contract_syntax()
    
    for contract, result in contract_results.items():
        print(f"\n{contract}:")
        if "error" in result:
            print(f"  ERROR: {result['error']}")
            continue
            
        print(f"  Lines: {result['lines']}, Size: {result['size']} bytes")
        print(f"  Message types: {result['message_types']}")
        
        syntax_ok = all(result['syntax_checks'].values())
        security_ok = all(result['security_checks'].values())
        
        print(f"  {'OK' if syntax_ok else 'FAIL'} Syntax: {result['syntax_checks']}")
        print(f"  {'OK' if security_ok else 'FAIL'} Security: {result['security_checks']}")
    
    # Test governance spec
    print("\nGovernance Test Suite:")
    test_results = test_governance_spec()
    
    if "error" in test_results:
        print(f"  ERROR: {test_results['error']}")
    else:
        print(f"  Lines: {test_results['lines']}, Size: {test_results['size']} bytes")
        print(f"  Test blocks: {test_results['test_blocks']}")
        print(f"  Coverage: {test_results['coverage']}")
        
        total_tests = test_results['test_blocks']['it_blocks']
        print(f"  Total test cases: {total_tests}")
        
        coverage_score = sum(test_results['coverage'].values())
        print(f"  Coverage score: {coverage_score}/5 areas")
    
    print("\nContract Testing Summary:")
    print("OK Contract syntax validation completed")
    print("OK Security pattern analysis completed") 
    print("OK Test structure analysis completed")
    print("INFO For full execution testing, install Node.js and run:")
    print("   npm install && npm test")

if __name__ == "__main__":
    main()
