namespace ResearchAvatarAgent.Api
{
    public static class ApiConfig
    {
        public const string DefaultServerBaseUrl = "http://127.0.0.1:8000";
        public const string UnityChatPath = "/api/v1/unity/chat";
        public const string LlmProvidersPath = "/api/v1/llm/providers";
        public const string LlmConfigPath = "/api/v1/llm/config";
        public const int DefaultTimeoutSeconds = 30;
    }
}
