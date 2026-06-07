# Third-party notices and attribution

The original code in this repository is licensed under the MIT License (see
[LICENSE](LICENSE)). It builds on and interoperates with the third-party work below.

## Magenta RealTime 2 (`magenta-rt`)

Copyright Google LLC. Licensed under the Apache License, Version 2.0
(<http://www.apache.org/licenses/LICENSE-2.0>).
Project: <https://github.com/magenta/magenta-realtime>

This repository installs and calls the `magenta-rt` package; it does not redistribute the
package's source. If the upstream C++ engine source (`port_src/`) is added to this
repository, those files retain their original Apache-2.0 license and per-file headers.

## Magenta RealTime 2 model weights

The model checkpoints (for example `mrt2_small.safetensors`) are downloaded at runtime
from HuggingFace and are subject to the model publisher's own license terms. They are not
included in this repository.

## VFX-JS (`@vfx-js/core`)

Licensed under the MIT License. Vendored at
`port/oneclick/ui/vendor/vfx-js.js` for the audio-reactive visualizer.
