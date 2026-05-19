.PHONY: demo review-demo proposal-demo review propose smoke

demo:
	./scripts/bootstrap-demo.sh

review-demo:
	./scripts/review-demo.sh

proposal-demo:
	./scripts/proposal-demo.sh

review:
	./scripts/brain-review.sh

propose:
	./scripts/propose-review.sh

smoke:
	./scripts/smoke-test.sh
