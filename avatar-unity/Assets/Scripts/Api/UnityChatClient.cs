using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace ResearchAvatarAgent.Api
{
    public sealed class ChatApiException : Exception
    {
        public long StatusCode { get; }
        public string ResponseBody { get; }

        public ChatApiException(long statusCode, string message, string responseBody)
            : base(message)
        {
            StatusCode = statusCode;
            ResponseBody = responseBody;
        }
    }

    public sealed class UnityChatClient : MonoBehaviour
    {
        [SerializeField]
        private string serverBaseUrl = ApiConfig.DefaultServerBaseUrl;

        [SerializeField]
        private string sessionId = "unity-demo";

        [SerializeField, Min(1)]
        private int timeoutSeconds = ApiConfig.DefaultTimeoutSeconds;

        [SerializeField]
        private string connectionTestMessage = "Hello from Unity";

        public async Task<ChatResponse> SendMessageAsync(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                throw new ArgumentException("Chat message must not be blank.", nameof(message));
            }

            if (string.IsNullOrWhiteSpace(sessionId))
            {
                throw new InvalidOperationException("Chat session ID must not be blank.");
            }

            var url = $"{serverBaseUrl.TrimEnd('/')}{ApiConfig.UnityChatPath}";
            var body = JsonUtility.ToJson(new ChatRequest(sessionId, message));
            var payload = Encoding.UTF8.GetBytes(body);

            using var request = new UnityWebRequest(url, UnityWebRequest.kHttpVerbPOST)
            {
                uploadHandler = new UploadHandlerRaw(payload),
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = timeoutSeconds,
            };
            request.SetRequestHeader("Content-Type", "application/json; charset=utf-8");

            var operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                throw new ChatApiException(
                    request.responseCode,
                    $"Chat request failed: {request.error}",
                    request.downloadHandler.text
                );
            }

            var response = JsonUtility.FromJson<ChatResponse>(request.downloadHandler.text);
            if (response == null ||
                string.IsNullOrWhiteSpace(response.request_id) ||
                response.emotion == null ||
                response.avatar == null)
            {
                throw new ChatApiException(
                    request.responseCode,
                    "Chat response did not match the expected protocol.",
                    request.downloadHandler.text
                );
            }

            return response;
        }

        [ContextMenu("Test Chat Connection")]
        private async void TestChatConnection()
        {
            try
            {
                var response = await SendMessageAsync(connectionTestMessage);
                Debug.Log($"Chat reply [{response.request_id}]: {response.reply}", this);
            }
            catch (Exception error)
            {
                Debug.LogException(error, this);
            }
        }
    }
}
