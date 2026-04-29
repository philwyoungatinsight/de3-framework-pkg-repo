# Re-runs a script whenever the trigger value changes.
# Used by null units that wrap Ansible/bash operations as Terraform resources,
# giving them a place in the Terragrunt DAG without bespoke step scripts.
#
# script_dir is stored in triggers (not just passed as var) so the destroy
# provisioner can reference it via self.triggers — vars are not accessible
# during destroy.
resource "null_resource" "this" {
  triggers = {
    trigger    = var.trigger
    script_dir = var.script_dir
  }

  provisioner "local-exec" {
    command = "${var.script_dir}/run --build"
  }

  # on_failure = continue ensures the resource is always removed from state
  # even if the cleanup script exits non-zero.  Without this, a failed
  # provisioner keeps the resource in state and blocks the next apply from
  # re-running the build script.
  provisioner "local-exec" {
    when       = destroy
    command    = "${self.triggers.script_dir}/run --clean 2>/dev/null || true"
    on_failure = continue
  }
}
