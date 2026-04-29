# Goal
- Track open items

# HIGH PRIORITY
- Make packages for new customer work.
  - Ml-Flow and all app dependencies
    - milvus, etcd, minio
    - mlflow
    - Postgres
  - Canonical python-docker-k8s app  
- Make packages for harbor (and initial k8s-pkg)
- Test (thoroughly) unit and package CRUD operations (copy, rename, etc) 

# MEDIUM PRIORITY

- k8s-pkg
  - update set_env.sh with a _KUBE_COFIG_DIR that is under _EPHEMERAL_DIR
  - Standardize on "kubeconfig" unit like the gke example
    - ideally, automatically write kubeconfig to sops (like the maas api key is handled)
  *- helm-package-unit (under kubeconfig unit)
    - ideally, use kubeconfig from sops
  - use helm-pack*age-unit/TF code)
    - port code to make alt-admin
    - Store KUBECONFIG in sops (automatically)
    - Optionally store under _EPHEMERAL_DIR in a dir that is
      output by the code so other packages can use it.
      Make this a well-known calculation so utils can easily use it.
      Consider extending override_cd for this.

# LOWER PRIORITY
- Helm package ports
  - most of the older code (from k8s-recipes)
    - nvidia-gpu-pkg
      - nvidia-nim-cache-unit
      - nvidia-nim-service-unit 
    - networking components
    - storage components
    - rancher-pkg
      - rancher ui
      - rke2
      - kubeconfig
    - k8s-generic-user-units (roles etc.)
- Use proper Packer Templates for MAAS, e.g.
  - Rocky 9 https://github.com/canonical/packer-maas/blob/main/rocky9/README.md are we using it? Update the code to use this
  - Rocky 10
  - test kairos and other OSes on physical machines
- KVM SERVER
  - Add package for KVM to make a host into a KVM server and
    create VMs via qemu/KVM on it. 
  - Support latest ubuntu and rocky
  - Use framework role feature to deploy
- DOCKER SERVER
  - same as KVM server but for docker (containers)

# Later
- add a gui to configure and run the framework repo manager
- add a gui to configure and run the package repo manager

# Arch Diagram (de3-gui)

Post-implementation improvements, roughly in priority order:

- **Additional export formats** — Mermaid (`graph TD`), GraphML, Graphviz DOT.
  Each format: add one entry to `_ARCH_EXPORT_FORMATS` + one generator function +
  one key in `_ARCH_GENERATORS`. No other code changes.
- **Named / timestamped export snapshots** — append a timestamp to the filename so
  successive saves don't overwrite each other (e.g. `arch-diagram-20260422-153000.drawio`).
  Could be a toolbar toggle: "overwrite" vs. "snapshot".
- **Node click → infra panel navigation** — clicking a leaf node in the Arch Diagram should
  open its unit's detail panel (same behaviour as clicking a unit row in the tree view).
  Wire `_ARCH_DIAGRAM_NODE_CLICK_JS` to dispatch `AppState.set_selected_path(node.id)`.
- **Unit-level icon override via YAML** — support `_arch_diagram_icon: "shape=..."` in a
  unit's `config_params` YAML, so individual units can override the `icon_map` lookup
  without touching `arch_diagram_config.yaml`.
- **`_arch_diagram_layer` override in YAML** — support `_arch_diagram_layer: <layer_id>` on
  individual units or subtrees to force them into a specific swimlane zone.
- **Auto-refresh on infra file changes** — watch `_config/*.yaml` + terragrunt files for
  changes and automatically rebuild `_ALL_NODES_CACHE` / `_DEPENDENCIES_CACHE` so the
  diagram reflects edits without restarting the app.
- **Multi-page draw.io export** — generate separate drawpyo pages per zone/layer within a
  single `.drawio` file, plus a summary overview page.
- **In-browser icon rendering** — React Flow currently shows boxes only. To show icons in
  the browser without draw.io: add custom `nodeTypes` (`leafNode`, `containerNode`) that
  render SVG icons. Requires JS component work; lower priority than draw.io export icons.
- **GUI editor for `arch_diagram_config.yaml`** — an in-app settings panel to edit layer
  definitions, icon mappings, and provider styles without touching the file manually.
- **diagrams.net self-hosting** — deploy draw.io app as a local container so the
  "Open in browser" link works in air-gapped environments.
