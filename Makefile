.PHONY: demo review-demo review smoke

demo:
	./scripts/bootstrap-demo.sh

review-demo:
	./scripts/review-demo.sh

review:
	./scripts/brain-review.sh

smoke:
	./scripts/smoke-test.sh
