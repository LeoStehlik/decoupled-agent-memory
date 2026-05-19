.PHONY: demo review-demo proposal-demo ledger-demo brief-demo review propose brief smoke

demo:
	./scripts/bootstrap-demo.sh

review-demo:
	./scripts/review-demo.sh

proposal-demo:
	./scripts/proposal-demo.sh

ledger-demo:
	./scripts/ledger-demo.sh

review:
	./scripts/brain-review.sh

propose:
	./scripts/propose-review.sh

brief:
	./scripts/brain-brief.sh

brief-demo:
	./scripts/brief-demo.sh

smoke:
	./scripts/smoke-test.sh
