output "script_hash" {
  description = "SHA-256 hash of the script that was run. Changes when the script is updated."
  value       = sha256(var.script)
}
