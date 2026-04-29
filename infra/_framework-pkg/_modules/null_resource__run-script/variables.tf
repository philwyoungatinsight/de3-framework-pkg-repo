variable "trigger" {
  description = "Opaque string. Changing this value triggers a re-run of the script. Typically a config/script hash, a dependency output ID, or a combination of both."
  type        = string
}

variable "script_dir" {
  description = "Absolute path to the script directory. Must contain a 'run' script that accepts a --build flag."
  type        = string
}
