using System;

namespace ResearchAvatarAgent.Api
{
    public static class EmotionLabels
    {
        public const string Neutral = "neutral";
        public const string Happy = "happy";
        public const string Sad = "sad";
        public const string Angry = "angry";
        public const string Relaxed = "relaxed";
        public const string Surprised = "surprised";
    }

    public static class AvatarActions
    {
        public const string Idle = "idle";
        public const string Nod = "nod";
        public const string Wave = "wave";
    }

    [Serializable]
    public sealed class ChatRequest
    {
        public string session_id;
        public string message;

        public ChatRequest(string sessionId, string userMessage)
        {
            session_id = sessionId;
            message = userMessage;
        }
    }

    [Serializable]
    public sealed class EmotionState
    {
        public string label;
        public float valence;
        public float arousal;
        public float intensity;
    }

    [Serializable]
    public sealed class AvatarCommand
    {
        public string expression;
        public string action;
        public float intensity;
        public int duration_ms;
    }

    [Serializable]
    public sealed class ChatResponse
    {
        public string request_id;
        public string reply;
        public EmotionState emotion;
        public AvatarCommand avatar;
    }
}
