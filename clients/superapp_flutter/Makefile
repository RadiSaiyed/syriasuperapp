SHELL := /bin/bash

# Usage:
#  make run-prod DEVICE="iPhone 17 Pro"
#  make build-ios-prod

DEFINES_FILE := dart_defines/prod.json

.PHONY: run-prod build-ios-prod build-apk-prod

run-prod:
	flutter pub get
	@if [ ! -f $(DEFINES_FILE) ]; then \
		echo "$(DEFINES_FILE) not found. Create it first."; exit 1; \
	fi
	@if [ -n "$(DEVICE)" ]; then \
		flutter run -d "$(DEVICE)" --dart-define-from-file=$(DEFINES_FILE); \
	else \
		flutter run --dart-define-from-file=$(DEFINES_FILE); \
	fi

build-ios-prod:
	flutter pub get
	@if [ ! -f $(DEFINES_FILE) ]; then \
		echo "$(DEFINES_FILE) not found. Create it first."; exit 1; \
	fi
	flutter build ios --release --no-codesign --dart-define-from-file=$(DEFINES_FILE)

# Optional (Android):
build-apk-prod:
	flutter pub get
	@if [ ! -f $(DEFINES_FILE) ]; then \
		echo "$(DEFINES_FILE) not found. Create it first."; exit 1; \
	fi
	flutter build apk --release --dart-define-from-file=$(DEFINES_FILE)

