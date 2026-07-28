from pptmaker.providers.models import ProviderConfig


PRESETS = {
    "deepseek": ProviderConfig(
        provider_id="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-pro",
    ),
    "kimi": ProviderConfig(
        provider_id="kimi",
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k",
    ),
    "qwen": ProviderConfig(
        provider_id="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    ),
    "custom": ProviderConfig(provider_id="custom", base_url="", model=""),
}
