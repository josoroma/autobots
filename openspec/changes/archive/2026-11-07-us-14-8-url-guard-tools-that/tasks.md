# Tasks

## 1. Guard (Refuse unsafe URLs before any request)

- [x] 1.1 Check scheme, userinfo, length and every DNS answer before a request, with an injectable resolver

## 2. Fetch (Revalidate every redirect; Cap size and time)

- [x] 2.1 Fetch hop by hop, checking each target, following at most three redirects, with size and time caps
- [x] 2.2 Cover the three scenarios with a fake resolver and transport
