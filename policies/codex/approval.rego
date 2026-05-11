package codex.approval

# Approval workflow policy.
# input.user:   { id, groups: [...], clearance }
# input.action: "submit" | "approve" | "reject" | "view"

default allow := false

# Admins may do anything.
allow {
    "admin" in input.user.groups
}

# Any authenticated user may submit a bundle for review.
allow {
    input.action == "submit"
    input.user.id != ""
}

# Any authenticated user may view pending items.
allow {
    input.action == "view"
    input.user.id != ""
}

# Only approvers and admins may approve or reject.
allow {
    input.action in {"approve", "reject"}
    "approver" in input.user.groups
}
