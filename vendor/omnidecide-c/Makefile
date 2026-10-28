# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# OmniDecide C - builds libomnidecide.a, the examples and the smoke test.
#
#   make               build build/libomnidecide.a
#   make examples      build the example programs into build/
#   make test          build and run the smoke test
#   make install       install the library and header (PREFIX=/usr/local)
#   make clean
#
# Override the compiler or flags as usual, e.g.
#   make CC=clang CFLAGS="-O2 -Wall -Wextra -Werror -pedantic"
#
# -std=c11 and -ffp-contract=off are ALWAYS applied: disabling floating
# point contraction is what keeps results bit-identical across compilers,
# optimization levels and machines.

CC      ?= cc
AR      ?= ar
CFLAGS  ?= -O2 -Wall -Wextra -pedantic
PREFIX  ?= /usr/local
BUILD   ?= build

ODK_CFLAGS := -std=c11 -ffp-contract=off
SRCS       := $(sort $(wildcard src/*.c))
OBJS       := $(SRCS:src/%.c=$(BUILD)/%.o)
LIB        := $(BUILD)/libomnidecide.a
EXAMPLES   := odk_demo quickstart languages learning long_context explain model
EXAMPLE_BINS := $(EXAMPLES:%=$(BUILD)/%)

.PHONY: all examples test install uninstall clean

all: $(LIB)

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude -Isrc -c $< -o $@

$(LIB): $(OBJS)
	$(AR) rcs $@ $(OBJS)

examples: $(EXAMPLE_BINS)

$(BUILD)/odk_demo: examples/odk_demo.c $(LIB)
$(BUILD)/quickstart: examples/quickstart.c $(LIB)
$(BUILD)/languages: examples/languages.c $(LIB)
$(BUILD)/learning: examples/learning.c $(LIB)
$(BUILD)/long_context: examples/long_context.c $(LIB)
$(BUILD)/explain: examples/explain.c $(LIB)
$(BUILD)/model: examples/model.c $(LIB)

$(EXAMPLE_BINS):
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude $< $(LIB) -lm -o $@

$(BUILD)/smoke_test: tests/smoke_test.c $(LIB)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude $< $(LIB) -lm -o $@

# The test's exit status is the make target's exit status.
test: $(BUILD)/smoke_test
	$(BUILD)/smoke_test

install: $(LIB)
	install -d $(DESTDIR)$(PREFIX)/lib $(DESTDIR)$(PREFIX)/include
	install -m 644 $(LIB) $(DESTDIR)$(PREFIX)/lib/libomnidecide.a
	install -m 644 include/omnidecide.h $(DESTDIR)$(PREFIX)/include/omnidecide.h

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/lib/libomnidecide.a \
	      $(DESTDIR)$(PREFIX)/include/omnidecide.h

clean:
	rm -rf $(BUILD)

# ---- Golden corpus (docs/GOLDEN.md) ----
GOLDEN ?= golden

.PHONY: golden golden-check hostile thread-probe docs-check version-check
golden: $(BUILD)/golden_tool
$(BUILD)/model_pack: tools/model_pack.c $(LIB)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude -Isrc tools/model_pack.c $(LIB) -lm -o $@
golden-check: $(BUILD)/golden_tool
	$(BUILD)/golden_tool check $(GOLDEN)
$(BUILD)/golden_tool: tests/golden_tool.c tests/golden_lang.h $(LIB)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude tests/golden_tool.c $(LIB) -lm -o $@
$(BUILD)/hostile_tool: tests/hostile_tool.c $(LIB)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude tests/hostile_tool.c $(LIB) -lm -o $@
hostile: $(BUILD)/hostile_tool
	$(BUILD)/hostile_tool
$(BUILD)/thread_probe: tests/thread_probe.c $(LIB)
	$(CC) $(ODK_CFLAGS) $(CFLAGS) -Iinclude tests/thread_probe.c $(LIB) -lm -lpthread -o $@
thread-probe: $(BUILD)/thread_probe
	$(BUILD)/thread_probe

# Relative markdown links must resolve (POSIX shell; no other tools needed).
docs-check:
	sh tests/check_links.sh

# Header macros, CMake version and CHANGELOG must agree.
version-check:
	sh tests/check_version.sh
