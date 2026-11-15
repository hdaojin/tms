BOOTSTRAP_DATA = [
    {
        "label": "预设 AI 提供商",
        "model": "ai.AIProviderSettings",
        "key_fields": ("provider",),
        "records": [
            {
                "provider": "zhipu",
                "name": "智谱 GLM",
                "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
                "__create_defaults__": {"adapter": "openai"},
            },
            {
                "provider": "xiaomi_mimo",
                "name": "小米 MiMo",
                "default_base_url": "https://api.xiaomimimo.com/v1",
                "__create_defaults__": {"adapter": "openai"},
            },
            {
                "provider": "doubao",
                "name": "豆包 Doubao Seed",
                "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "__create_defaults__": {"adapter": "openai"},
            },
            {
                "provider": "kimi",
                "name": "Kimi",
                "default_base_url": "https://api.moonshot.cn/v1",
                "__create_defaults__": {"adapter": "openai"},
            },
            {
                "provider": "minimax",
                "name": "MiniMax",
                "default_base_url": "https://api.minimax.cn/v1",
                "__create_defaults__": {"adapter": "openai"},
            },
        ],
    },
    {
        "label": "预设 AI 模型选项",
        "model": "ai.AIModelOption",
        "key_fields": ("provider", "model_id"),
        "records": [
            {"provider": "dashscope", "model_id": "qwen3.8-flash", "name": "Qwen 3.8 Flash"},
            {"provider": "dashscope", "model_id": "qwen3.8-max", "name": "Qwen 3.8 Max"},
            {"provider": "zhipu", "model_id": "glm-5.3", "name": "GLM-5.3"},
            {"provider": "xiaomi_mimo", "model_id": "mimo-v2.6-flash", "name": "MiMo V2.6 Flash"},
            {"provider": "xiaomi_mimo", "model_id": "mimo-v2.6-pro", "name": "MiMo V2.6 Pro"},
            {"provider": "xiaomi_mimo", "model_id": "mimo-v2.6-pro-ultraspeed", "name": "MiMo V2.6 Pro UltraSpeed"},
            {"provider": "doubao", "model_id": "doubao-seed-2-1-lite-260915", "name": "Doubao Seed 2.1 Lite"},
            {"provider": "doubao", "model_id": "doubao-seed-2-1-pro-260915", "name": "Doubao Seed 2.1 Pro"},
            {"provider": "kimi", "model_id": "kimi-k3.1-pro", "name": "Kimi K3.1 Pro"},
            {"provider": "minimax", "model_id": "MiniMax-M3.1-Flash", "name": "MiniMax M3.1 Flash"},
            {"provider": "minimax", "model_id": "MiniMax-M3", "name": "MiniMax M3"},
        ],
    },
]
