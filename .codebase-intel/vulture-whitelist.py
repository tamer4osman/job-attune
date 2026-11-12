# Vulture whitelist - names vulture reports as unused but which are in fact
# consumed by frameworks or kept deliberately as public API surface.
#
# Passed to every `vulture` run (see scripts/codebase_intel.py and
# docs/CODEBASE-INTEL.md). Keep every entry paired with a reason.

# --- server.py: http.server / ThreadingHTTPServer framework hooks -----------
# BaseHTTPRequestHandler dispatches do_GET/do_POST/do_HEAD by name and calls
# log_message() on every request; server_version/protocol_version/daemon_threads
# are read by the http.server / socketserver machinery, never by our code.
from server import AttuneHandler  # noqa: F401 - import only to reference hooks

AttuneHandler.daemon_threads
AttuneHandler.log_message
AttuneHandler.protocol_version
AttuneHandler.server_version
AttuneHandler.do_GET
AttuneHandler.do_POST
AttuneHandler.do_HEAD

# --- attune-engine/ckernel.py: upstream API parity --------------------------
# The vendored omnidecide-c binding keeps the upstream constructor signature:
# cache_dir/use_cuda are accepted and stored for parity (documented in the
# class docstring), and `providers` is a compat property that mirrors the
# reference implementation's backend list.
from ckernel import DeterministicDecisionKernel  # noqa: F401

DeterministicDecisionKernel._use_cuda
DeterministicDecisionKernel.providers

# --- attune-engine/make_report.py: reportlab global configuration -----------
# `rl_config.invariant = 1` is a reportlab package setting (byte-stable PDFs),
# not an attribute definition of ours.
import reportlab.rl_config as _rl_config  # noqa: F401

_rl_config.invariant

# cache_dir is a keyword of DeterministicDecisionKernel.__init__ (signature
# parity, see the class docstring); a bare reference marks the parameter as
# deliberately accepted-and-ignored.
cache_dir

# --- attune-engine/make_report.py: legacy aliases -----------------------------
# SLATE_900 and ENGINE_EMERALD are kept as aliases for INK and ORANGE
# respectively — they preserve the public module surface for any external
# code that imports them by the old name. Bare references mark them as
# deliberately retained.
SLATE_900
ENGINE_EMERALD

# --- scripts/convert_fonts.py: fontTools TTFont attributes ---------------------
# sfntVersion, flavor and flavorData are set on the TTFont object in _to_ttf()
# to control the output format (TrueType vs WOFF2). fontTools reads them during
# save(); they are not "used" in the conventional sense within this file.
sfntVersion
flavor
flavorData

# --- scripts/test_pdf_theme.py: theme color definitions -------------------------
# PAPER_HEX, FOREST_HEX, ORANGE_HEX are theme color definitions for PDF
# export testing. They document the mapping between CSS tokens and reportlab
# normalized RGB values; kept for reference and potential future use.
PAPER_HEX
FOREST_HEX
ORANGE_HEX

# --- attune-engine/wasm_kernel.py: WASM export surface -------------------------
# kernel_count is a WASM export (odkw_kernel_count) loaded alongside the other
# kernel symbols. It is part of the WASM module's public export surface and
# must remain bound to the instance for parity with the native bridge, even
# though the Python layer does not currently call it directly.
from wasm_kernel import _WasmHost  # noqa: F401

_WasmHost.kernel_count

# --- attune-engine/spine_kernel.py: F4 spine features (future calibration loop) ---
# ingest_observation and calibrate are SpineContext methods for the F4
# observation-log calibration report feature (docs/SPINE-FEATURES.md). They are
# part of the API surface but not yet enabled by default - the pipeline will
# call them when the calibration loop feature is activated.
from spine_kernel import SpineContext  # noqa: F401

SpineContext.ingest_observation
SpineContext.calibrate
