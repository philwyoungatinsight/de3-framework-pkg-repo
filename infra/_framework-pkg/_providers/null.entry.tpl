# Entry fragment injected into required_providers {} by root.hcl when a unit
# declares _extra_providers: ["null"]. See docs/framework/unit_params.md.
null = { source = "hashicorp/null", version = "~> 3.0" }
