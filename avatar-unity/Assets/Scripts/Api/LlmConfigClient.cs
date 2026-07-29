using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace ResearchAvatarAgent.Api
{
    public sealed class LlmConfigApiException : Exception
    {
        public long StatusCode { get; }
        public string ResponseBody { get; }

        public LlmConfigApiException(long statusCode, string message, string responseBody)
            : base(message)
        {
            StatusCode = statusCode;
            ResponseBody = responseBody;
        }
    }

    public sealed class LlmConfigClient : MonoBehaviour
    {
        [SerializeField]
        private string serverBaseUrl = ApiConfig.DefaultServerBaseUrl;

        [SerializeField, Min(1)]
        private int timeoutSeconds = ApiConfig.DefaultTimeoutSeconds;

        public async Task<LlmProvidersResponse> GetProvidersAsync()
        {
            var response = await SendAsync<LlmProvidersResponse>(
                ApiConfig.LlmProvidersPath,
                UnityWebRequest.kHttpVerbGET
            );
            if (response.providers == null)
            {
                throw InvalidResponse("Provider response does not contain a providers list.");
            }

            return response;
        }

        public async Task<LlmConfigResponse> ConfigureAsync(LlmConfigRequest config)
        {
            if (config == null)
            {
                throw new ArgumentNullException(nameof(config));
            }

            if (string.IsNullOrWhiteSpace(config.provider))
            {
                throw new ArgumentException("LLM provider must not be blank.", nameof(config));
            }

            var response = await SendAsync<LlmConfigResponse>(
                ApiConfig.LlmConfigPath,
                UnityWebRequest.kHttpVerbPOST,
                config
            );
            if (string.IsNullOrWhiteSpace(response.provider) ||
                string.IsNullOrWhiteSpace(response.model))
            {
                throw InvalidResponse("Config response does not contain provider and model.");
            }

            return response;
        }

        private async Task<T> SendAsync<T>(string path, string method, object body = null)
        {
            var url = $"{serverBaseUrl.TrimEnd('/')}{path}";
            using var request = new UnityWebRequest(url, method)
            {
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = timeoutSeconds,
            };

            if (body != null)
            {
                request.uploadHandler = new UploadHandlerRaw(
                    Encoding.UTF8.GetBytes(JsonUtility.ToJson(body))
                );
                request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");
            }

            var operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                throw new LlmConfigApiException(
                    request.responseCode,
                    $"LLM API request failed: {request.error}",
                    request.downloadHandler.text
                );
            }

            var response = JsonUtility.FromJson<T>(request.downloadHandler.text);
            if (response == null)
            {
                throw InvalidResponse("LLM API response is not valid JSON.");
            }

            return response;
        }

        private static LlmConfigApiException InvalidResponse(string message)
        {
            return new LlmConfigApiException(200, message, string.Empty);
        }
    }
}
