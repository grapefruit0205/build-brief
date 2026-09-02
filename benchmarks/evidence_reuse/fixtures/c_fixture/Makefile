CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror

.PHONY: test
test:
	mkdir -p build
	$(CC) $(CFLAGS) -Iinclude src/app.c src/shared.c tests/test_app.c -o build/test_app
	./build/test_app
