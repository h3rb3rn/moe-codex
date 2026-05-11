package codex.data_markings

# Data classification hierarchy (ascending sensitivity).
# A user's clearance must be >= the dataset's classification level.
classification_level := {
    "PUBLIC":       0,
    "INTERNAL":     1,
    "RESTRICTED":   2,
    "CONFIDENTIAL": 3,
    "SECRET":       4,
}

default user_clearance_level := 0

user_clearance_level := classification_level[input.user.clearance] {
    input.user.clearance != ""
}

default dataset_classification_level := 0

dataset_classification_level := classification_level[input.dataset.classification] {
    input.dataset.classification != ""
}

# allow if user clearance >= dataset classification
default allow := false

allow {
    user_clearance_level >= dataset_classification_level
}
