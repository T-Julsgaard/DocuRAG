---
summary: "How customers update their card or payment method, and what happens when a payment fails."
category: "Billing"
tags: "payment method, card, credit card, update card, failed payment, declined"
url: "https://help.nimbus.example/billing/payment-method"
---

# Update payment method

## Update a card

1. Open **Settings → Billing → Payment method**.
2. Click **Update** and enter the new card details.
3. Save. The new card is charged at the next renewal.

Accepted: **Visa, Mastercard, American Express**, and PayPal.

## When a payment fails

We retry a failed charge on this schedule:

| Attempt | When |
|---|---|
| 1st retry | **Day 1** after failure |
| 2nd retry | **Day 3** |
| 3rd retry | **Day 7** |

- The account stays on its paid plan during retries (a **7-day grace period**).
- If all retries fail, the account is downgraded to **Free** and files over the
  5 GB limit become **read-only** until storage is freed or payment succeeds.
- No files are ever deleted due to a failed payment.
