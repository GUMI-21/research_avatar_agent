using System;

namespace ResearchAvatarAgent.Api
{
    public static class LlmProviderIds
    {
        public const string Mock = "mock";
        public const string OpenAi = "openai";
        public const string Gemini = "gemini";
        public const string DeepSeek = "deepseek";
    }

    [Serializable]
    public sealed class LlmConfigRequest
    {
        public string provider;
        public string api_key;
        public string model;
        public string base_url;

        public LlmConfigRequest(
            string providerId,
            string modelId = null,
            string apiKey = null,
            string baseUrl = null
        )
        {
            provider = providerId;
            model = modelId;
            api_key = apiKey;
            base_url = baseUrl;
        }
    }

    [Serializable]
    public sealed class LlmConfigResponse
    {
        public string provider;
        public string model;
        public string base_url;
        public bool api_key_configured;
        public string api_key_source;
    }

    [Serializable]
    public sealed class LlmModelOption
    {
        public string model;
        public string display_name;
        public LlmConfigRequest config;
    }

    [Serializable]
    public sealed class LlmProviderOption
    {
        public string provider;
        public string display_name;
        public string default_model;
        public bool allow_custom_model;
        public LlmModelOption[] models;
    }

    [Serializable]
    public sealed class LlmProvidersResponse
    {
        public LlmProviderOption[] providers;
    }
}
