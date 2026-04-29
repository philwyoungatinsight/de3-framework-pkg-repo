# Goal
- Track open items

# NOTES
- rename _framework-pkg to framework-pkg for clarity

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
  