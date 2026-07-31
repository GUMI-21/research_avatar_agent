using System;
using System.Text;
using ResearchAvatarAgent.Api;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    [RequireComponent(typeof(UnityChatClient))]
    public sealed class ChatPanelController : MonoBehaviour
    {
        [SerializeField]
        private TMP_InputField messageInput;

        [SerializeField]
        private TMP_Text historyText;

        [SerializeField]
        private Button sendButton;

        [SerializeField]
        private ScrollRect historyScroll;

        private readonly StringBuilder history = new();
        private UnityChatClient chatClient;
        private bool isSending;

        public void Bind(
            TMP_InputField input,
            TMP_Text chatHistory,
            Button button,
            ScrollRect scroll
        )
        {
            messageInput = input;
            historyText = chatHistory;
            sendButton = button;
            historyScroll = scroll;
        }

        private void Awake()
        {
            chatClient = GetComponent<UnityChatClient>();
            if (messageInput == null ||
                historyText == null ||
                sendButton == null ||
                historyScroll == null)
            {
                Debug.LogError("Chat panel UI references are incomplete.", this);
                enabled = false;
            }
        }

        private void OnEnable()
        {
            if (sendButton == null || messageInput == null)
            {
                return;
            }

            sendButton.onClick.AddListener(SendCurrentMessage);
            messageInput.onSubmit.AddListener(SubmitFromKeyboard);
        }

        private void OnDisable()
        {
            sendButton?.onClick.RemoveListener(SendCurrentMessage);
            messageInput?.onSubmit.RemoveListener(SubmitFromKeyboard);
        }

        private void SubmitFromKeyboard(string _)
        {
            SendCurrentMessage();
        }

        // Unity UI events require a void callback, so errors are handled inside.
        private async void SendCurrentMessage()
        {
            var message = messageInput.text.Trim();
            if (isSending || string.IsNullOrEmpty(message))
            {
                return;
            }

            isSending = true;
            messageInput.text = string.Empty;
            SetInputEnabled(false);
            AppendHistory("You", message);

            try
            {
                var response = await chatClient.SendMessageAsync(message);
                AppendHistory("Avatar", response.reply);
            }
            catch (Exception error)
            {
                AppendHistory("System", $"Request failed: {error.Message}");
                Debug.LogException(error, this);
            }
            finally
            {
                isSending = false;
                SetInputEnabled(true);
                messageInput.ActivateInputField();
            }
        }

        private void SetInputEnabled(bool value)
        {
            messageInput.interactable = value;
            sendButton.interactable = value;
        }

        private void AppendHistory(string speaker, string message)
        {
            if (history.Length > 0)
            {
                history.AppendLine();
            }

            history.AppendLine($"{speaker}:");
            history.Append(message);
            historyText.SetText(history.ToString());

            // Layout updates one frame late; force it before scrolling to the bottom.
            Canvas.ForceUpdateCanvases();
            historyScroll.verticalNormalizedPosition = 0f;
        }
    }
}
