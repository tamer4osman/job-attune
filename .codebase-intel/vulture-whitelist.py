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
