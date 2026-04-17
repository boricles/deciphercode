# Archaeology Report

**Commits:** 847 | **Period:** 2021-03-15 to 2024-11-02 | **Contributors:** 12

## Top Contributors

| Contributor | Commits |
|---|---|
| Sarah Chen | 412 |
| Marcus Rivera | 198 |
| Alex Kim | 87 |
| Jordan Patel | 54 |
| dependabot[bot] | 38 |
| Chris Wong | 22 |

## Change Hotspots

| File | Changes |
|---|---|
| `orders/views.py` | 89 |
| `products/models.py` | 67 |
| `settings.py` | 58 |
| `payments/views.py` | 52 |
| `requirements.txt` | 45 |
| `orders/serializers.py` | 41 |
| `accounts/views.py` | 38 |

## Analysis

### Evolution Timeline

The project went through three distinct phases:

**Phase 1: Foundation (March - August 2021)** - Sarah Chen built the core structure: accounts, products, and basic order flow. Commits were frequent (daily) and focused on getting the Django apps wired up. The initial architecture was clean with good separation.

**Phase 2: Feature Expansion (September 2021 - June 2022)** - Marcus Rivera joined and built out the payments integration (Stripe) and shipping module. This was the most active period with both developers pushing daily. The `orders/views.py` hotspot originates here, as checkout logic was iterated on heavily.

**Phase 3: Maintenance (July 2022 - Present)** - Commit frequency dropped significantly. Most recent commits are dependency updates (dependabot) and minor bug fixes. The last feature commit was in March 2024.

### Key Contributors

Sarah Chen is the original architect and primary maintainer with nearly half of all commits. Marcus Rivera was the second core developer who built the payment and shipping systems. Other contributors made smaller, focused contributions, suggesting a small core team with occasional help.

### Tech Debt Hotspots

- **`orders/views.py` (89 changes):** The most changed file in the project. This strongly suggests the checkout/order logic is unstable or poorly abstracted. Likely a candidate for refactoring into smaller service modules.
- **`settings.py` (58 changes):** Configuration churn indicates the deployment setup evolved significantly and may still have inconsistencies.
- **`payments/views.py` (52 changes):** Frequent changes to payment handling suggest either evolving Stripe API requirements or fragile integration code.

### Observations

- The project appears to be in maintenance mode since mid-2022. No major features have been added in over a year.
- Dependabot is active, which is positive for security, but many PRs appear to be merged without review.
- No evidence of CI/CD configuration in the commit history.
- The ratio of test commits to feature commits is very low, consistent with the finding that test coverage is minimal.
