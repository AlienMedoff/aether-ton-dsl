# Contributing to Aether OS + TON TX DSL

Thank you for considering contributing to our project! We welcome contributions from the community.

## How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/AlienMedoff/aether-ton-dsl.git
cd aether-ton-dsl
```

### 2. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number
```

### 3. Make Your Changes
- Follow the existing code style
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass

### 4. Run Tests and Checks
```bash
# Python tests
python -m pytest tests/ -v

# Contract tests  
npm test

# Security checks
pip-audit
bandit -r .
```

### 5. Submit a Pull Request
- Push to your fork
- Create a PR against `main` branch
- Fill out the PR template completely
- Wait for review

## Code Style

### Python
- Follow PEP 8
- Use Black for formatting
- Maximum line length: 88 characters
- Add type hints where appropriate

### Smart Contracts (Tact)
- Follow Tact best practices
- Use meaningful variable names
- Add comments for complex logic
- Keep functions small and focused

### Documentation
- Use clear, concise language
- Include examples for new features
- Update README if needed
- Follow existing format

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (optional)

### Local Development
```bash
# Python environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
npm install

# Run tests
python -m pytest
npm test
```

## Types of Contributions

### Bug Fixes
- Describe the bug clearly
- Include steps to reproduce
- Add tests that cover the fix
- Update documentation if needed

### New Features
- Open an issue first to discuss
- Follow the existing architecture
- Include comprehensive tests
- Update documentation

### Documentation
- Fix typos and grammar
- Improve clarity
- Add examples
- Translate if possible

### Smart Contracts
- Test thoroughly on testnet
- Include gas optimization
- Add security considerations
- Document contract interfaces

## Security Considerations

### Before Contributing
- Review our [Security Policy](SECURITY.md)
- Never commit secrets or private keys
- Use secure coding practices
- Consider edge cases and attack vectors

### Smart Contract Security
- Follow TON security best practices
- Use proper access controls
- Implement fail-safes
- Test with various scenarios

## Testing

### Unit Tests
- Test individual functions
- Cover edge cases
- Mock external dependencies
- Aim for high coverage

### Integration Tests
- Test component interactions
- Include real-world scenarios
- Test with TON testnet
- Verify end-to-end flows

### Smart Contract Tests
- Test all contract functions
- Verify access controls
- Test with various inputs
- Check gas optimization

## Review Process

### What We Look For
- Code quality and style
- Test coverage
- Security considerations
- Performance impact
- Documentation completeness

### Review Timeline
- Initial review: 2-3 business days
- Additional rounds: As needed
- Merge: After all checks pass

## Community Guidelines

### Code of Conduct
- Be respectful and constructive
- Welcome newcomers
- Focus on what is best for the community
- Show empathy toward other community members

### Communication
- Use GitHub issues for questions
- Join our Telegram community
- Participate in discussions
- Help others when you can

## Getting Help

### Resources
- [Documentation](README.md)
- [Security Policy](SECURITY.md)
- [API Reference](docs/api.md)
- [Examples](examples/)

### Support Channels
- GitHub Issues: Bug reports and feature requests
- Telegram: Community discussion
- Discord: Development chat
- Email: support@aether-os.com

## Recognition

### Contributors
- Listed in README.md
- Mentioned in release notes
- Invited to contributor channel
- Eligible for contributor rewards

### Types of Contributions
- Code: Patches, new features, bug fixes
- Documentation: Improvements, translations
- Design: UI/UX improvements
- Community: Support, moderation, advocacy

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).

---

Thank you for contributing to Aether OS + TON TX DSL! 🚀
