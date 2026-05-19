.PHONY: demo smoke

demo:
	./scripts/bootstrap-demo.sh

smoke:
	./scripts/smoke-test.sh
