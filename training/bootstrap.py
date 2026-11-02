from datetime import time

BOOTSTRAP_DATA = [
    {
        "label": "默认训练时段",
        "model": "training.TrainingPeriodConfig",
        "key_fields": ("period",),
        "records": [
            {"period": "early", "start_time": time(8, 10), "end_time": time(8, 50)},
            {"period": "morning", "start_time": time(9), "end_time": time(12)},
            {"period": "afternoon", "start_time": time(14), "end_time": time(16, 30)},
            {"period": "evening", "start_time": time(18, 30), "end_time": time(20, 30)},
        ],
    },
]
