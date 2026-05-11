package codex.catalog

import data.codex.data_markings

# Catalog access policy.
# input.user:    { id, groups: [...], clearance }
# input.dataset: { name, namespace, classification, owner_group }
# input.action:  "read" | "write" | "delete"

default allow := false

# Admins may do anything.
allow {
    "admin" in input.user.groups
}

# Read access: user clearance must satisfy data marking.
allow {
    input.action == "read"
    data.codex.data_markings.allow with input as {
        "user":    input.user,
        "dataset": input.dataset,
    }
}

# Write access: user must belong to the dataset's owner group (or be admin).
allow {
    input.action == "write"
    input.dataset.owner_group != ""
    input.dataset.owner_group in input.user.groups
    data.codex.data_markings.allow with input as {
        "user":    input.user,
        "dataset": input.dataset,
    }
}

# Delete access: only admins (already covered above).
