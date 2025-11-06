# Open Source Contribution Strategy (PRIVATE)

**Created**: 2025-11-04
**Status**: Planning
**Visibility**: PRIVATE - Not for repository

## Context

Fork: `6R1M5L07H/AiogramShopBot` (429 commits ahead)
Upstream: `ilyarolf/AiogramShopBot` (404 commits ahead)

Goal: Contribute features back to upstream while maintaining fork autonomy.

## Problem Analysis

### Technical Situation
- **Massive Divergence**: 429 commits in fork, 404 in upstream
- **Different Focus**:
  - Fork: Enterprise features (Strike, Shipping, Order Management, Security)
  - Upstream: Maintenance mode (README updates, minor fixes)
- **Rebase Complexity**: 3-5 days effort, high conflict risk

### Social Situation
- ilyarolf seems hesitant about new features
- Last major features from ilyarolf: Docker, KryptoExpress
- Recent activity: Mostly maintenance and documentation

## Developed Features (Evaluation)

| Feature | Complexity | Business Value | Upstream Accept Chance |
|---------|-----------|----------------|----------------------|
| Security Hardening | LOW | HIGH | 90% - Bug fixes always welcome |
| Strike System | MEDIUM | HIGH | 75% - Clear abuse prevention |
| Order Management | MEDIUM | HIGH | 70% - Admin needs this |
| Unified Notifications | MEDIUM | HIGH | 60% - Code quality |
| Return to Category UX | LOW | MEDIUM | 80% - Simple UX fix |
| Invoice-based Payment | HIGH | HIGH | 40% - Complex, risky |
| Shipping Management | HIGH | MEDIUM | 20% - Niche (physical items) |

## Strategy Options

### Option 1: Feature-by-Feature PRs (Recommended)

**Approach**: Submit small, focused PRs in strategic order

**Phase 1: Test the Waters** (Week 1-2)
1. Create discussion issue on ilyarolf repo:
   - "Discussion: Contribution of enterprise features"
   - List available features
   - Ask which align with roadmap
2. Wait for response (2 weeks timeout)
   - Positive: Continue to Phase 2
   - Negative: Fork stays independent
   - No response: Assume inactive, fork independent

**Phase 2: Easy Wins** (Week 3-4)
PR #1: Security Hardening
- Changes: Config validation, HTML injection fix, HTTPS tunnel
- Size: Small (~200 LOC)
- Risk: Low (bug fixes)
- Argument: "Critical security vulnerabilities"

**Phase 3: Value Adds** (Week 5-8)
PR #2: Strike System
- Changes: Strike tracking, auto-ban, grace period
- Size: Medium (~800 LOC)
- Risk: Medium (new feature)
- Argument: "Prevents order abuse/spam"

PR #3: Order Management
- Changes: Order list, filters, payment history
- Size: Medium (~1200 LOC)
- Risk: Medium (admin feature)
- Argument: "Essential admin tool"

**Phase 4: Quality Improvements** (Week 9-12)
PR #4: Unified Notifications
- Changes: InvoiceFormatter, consistent messages
- Size: Medium (~600 LOC)
- Risk: Low (refactoring)
- Argument: "Code quality, DRY principle"

**Phase 5: Niche Features** (Optional)
PR #5: Shipping Management
- Changes: Physical item support, shipping addresses
- Size: Large (~2000 LOC)
- Risk: High (fundamental change)
- Argument: "Enables physical goods shops"
- Note: Only submit if previous PRs accepted

### Option 2: Fork as Independent Distribution

**Accept Reality**: Fork is a separate product

**Branding**:
- `AiogramShopBot` (ilyarolf) - Vanilla/Community Edition
- `AiogramShopBot-Professional` (6R1M5L07H) - Enterprise Edition

**Features**:
- All enterprise features included
- Faster iteration (no upstream approval needed)
- Target audience: Professional shops (physical + digital)

**Upstream Contribution**:
- Cherry-pick individual fixes (security, bugs)
- Don't force features
- Maintain compatibility where possible

**Marketing**:
- README: "Extended version with enterprise features"
- Comparison table vs upstream
- Use cases: Physical goods shops, high-volume shops

### Option 3: Merge Selected Features

**Hybrid Approach**: Keep most features in fork, only merge universally useful ones

**Merge to Upstream**:
- Security fixes (always)
- Bug fixes (always)
- UX improvements (selectively)

**Keep in Fork**:
- Strike System (opinionated policy)
- Shipping Management (niche use case)
- Order Management (maybe too enterprise)

## PR Template (for upstream)

```markdown
## Description
[Clear, concise description of the feature/fix]

## Motivation
[Why this is needed - business case or bug impact]

## Changes
- [Bullet point list of changes]
- [Keep it factual and concise]

## Testing
- [ ] Manual testing completed
- [ ] No existing functionality broken
- [ ] Backwards compatible

## Screenshots (if UI changes)
[Add screenshots]

## Configuration
[If config changes needed, document them]

## Migration
[If database/breaking changes, provide migration path]

## Checklist
- [ ] Code follows existing style
- [ ] No hardcoded values (uses config)
- [ ] Localization strings added (en.json, de.json)
- [ ] No TODOs or debug code
- [ ] Commit messages follow convention
- [ ] Ready for review

Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

Wait, remove the Generated with Claude Code footer per user instructions!

```markdown
## Checklist
- [ ] Code follows existing style
- [ ] No hardcoded values (uses config)
- [ ] Localization strings added (en.json, de.json)
- [ ] No TODOs or debug code
- [ ] Commit messages follow convention
- [ ] Ready for review
```

## Risk Assessment

### High Risk Scenarios
1. **Mass Rejection**: All PRs rejected → Fork stays independent (acceptable)
2. **Partial Acceptance**: Some PRs merged, creates maintenance burden
3. **Delayed Response**: PRs sit for months → Fork diverges further
4. **Breaking Changes**: Upstream changes break fork → Merge conflicts

### Mitigation
1. **Start Small**: Security PR tests the waters (low investment)
2. **Stay Independent**: Don't wait for upstream, keep developing
3. **Version Tags**: Tag fork versions (v4.0-professional) for stability
4. **Documentation**: Document differences between fork and upstream

## Decision Matrix

### When to Contribute Upstream:
- Security fixes (always)
- Bug fixes (always)
- Feature is universally useful (strike system, order management)
- Small, reviewable changes (<500 LOC per PR)
- ilyarolf shows interest

### When to Keep in Fork:
- Niche features (physical shipping)
- Large, complex features (invoice system)
- Opinionated changes (strike policies)
- ilyarolf shows no interest/response

## Long-term Vision

### Best Case (Optimistic)
- PRs accepted regularly
- Become co-maintainer
- Fork features merged over 6-12 months
- Unified project again

### Realistic Case (Expected)
- Some PRs accepted (security, small features)
- Fork stays semi-independent
- Cherry-pick fixes between repos
- Two distributions coexist

### Worst Case (Acceptable)
- No PRs accepted
- Fork fully independent
- Market as "Professional Edition"
- Build separate community

## Current Decision (2025-11-04)

**Immediate Action**:
1. Finalize Order Management feature in fork
2. Eliminate Buy entity (technical debt cleanup)
3. Focus on fork stability and quality

**Next Steps** (after Order Management complete):
1. Create discussion issue on ilyarolf repo
2. Wait 2 weeks for response
3. If positive: Prepare security PR
4. If negative/no response: Continue fork independently

**No Rebase**: Too risky, too costly (3-5 days). Not worth it unless ilyarolf explicitly requests it for PRs.

## Notes

- This is a marathon, not a sprint
- Open source is about patience and collaboration
- Fork independence is not failure - it's pragmatism
- Focus on code quality regardless of upstream acceptance
