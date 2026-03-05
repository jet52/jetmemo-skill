# TODO

- [ ] **Agent D: Add web fallback for opinion lookups.** When `~/refs/opin/` is absent, Agent D doesn't launch and the memo lacks precedent verification entirely. Add a web fallback using ndcourts.gov search (`https://www.ndcourts.gov/supreme-court/opinions?search={citation}`) so Agent D can still verify cited opinions and extract holdings. Model after the existing NDCC/NDAC web fallback pattern in Agent E.
