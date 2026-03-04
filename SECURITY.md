# Security Policy

## Supported Versions

| Version | Supported |
| ------- | ---------- |
| main | ✅ |
| v1.0.0 | ✅ |
| older | ❌ |

## Reporting a Vulnerability

If you discover a security issue in this project, please report it responsibly:

- **Email**: security@aether-os.com
- **PGP Key**: Available on request
- **Do NOT** open public GitHub issues for vulnerabilities
- **Provide**: Detailed steps to reproduce the issue

We will respond within 72 hours and work on a fix as soon as possible.

## Security Best Practices

### For Developers
- Never commit private keys or secrets
- Use `.env` files for local configuration (in `.gitignore`)
- Run `pip-audit` and `safety` before submitting PRs
- Use pre-commit hooks for linting and security checks
- Review all smart contract changes carefully

### For Operators
- Use hardware wallets for guardian keys
- Rotate API keys regularly
- Monitor timelock periods
- Keep software updated

### For Users
- Verify contract addresses on TON Explorer
- Use official interfaces only
- Be cautious of phishing attempts
- Keep your private keys secure

## Security Features

### Smart Contract Security
- **Timelock Governance**: 48h delay for critical changes
- **Multi-signature Oracle**: Ed25519 multisig protection
- **Guardian System**: 2-key security for Vault operations
- **Rollback Protection**: Automatic transaction rollback on failures

### System Security
- **Input Validation**: All inputs validated and sanitized
- **Access Control**: Role-based permissions
- **Audit Logging**: Complete syscall tracking
- **Rate Limiting**: Protection against abuse

## Known Security Considerations

### Dependencies
- Python dependencies are audited weekly
- Node.js packages are scanned for vulnerabilities
- Docker images are built from minimal base images

### Network Security
- TON API endpoints use HTTPS only
- All communications are encrypted
- No plaintext credentials in logs

### Smart Contract Risks
- Oracle manipulation risk (mitigated by multisig)
- Guardian key compromise (mitigated by 2-key requirement)
- Timelock bypass attempts (prevented by contract design)

## Security Audits

### Past Audits
- **Internal Audit**: v1.0.0 - Passed ✅
- **Community Review**: Ongoing ⏳

### Future Audits
- Planning external audit for v1.1.0
- Seeking third-party security assessment
- Bug bounty program in development

## Incident Response

### Severity Levels
- **Critical**: System compromise, fund loss
- **High**: Significant functionality impact
- **Medium**: Limited functionality impact
- **Low**: Minor issues, no user impact

### Response Time
- **Critical**: 24 hours
- **High**: 48 hours  
- **Medium**: 72 hours
- **Low**: 1 week

## Security Tools Used

- **Static Analysis**: Bandit, Slither (adapted for Tact)
- **Dependency Scanning**: pip-audit, npm audit
- **Container Security**: Trivy scans
- **Smart Contract Analysis**: Custom Tact analyzer
- **Runtime Protection**: Input validation, access controls

## Responsible Disclosure

We follow responsible disclosure principles:

1. **Acknowledge** receipt within 24 hours
2. **Assess** severity within 48 hours
3. **Fix** critical issues within 7 days
4. **Disclose** after fix is deployed
5. **Credit** researchers who report issues

## Security Contacts

- **Security Team**: security@aether-os.com
- **PGP Key**: Available on request
- **Bug Bounty**: Coming soon
- **Security Chat**: Matrix channel (private)

---

**Remember**: Security is everyone's responsibility. If you see something, say something.
