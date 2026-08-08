using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    [DefaultExecutionOrder(-100)]
    [RequireComponent(typeof(ChatPanelController))]
    public sealed class ChatPanelViewBuilder : MonoBehaviour
    {
        [SerializeField]
        private string panelTitle = "Research Avatar";

        private void Awake()
        {
            EnsureEventSystem();
            var canvas = CreateCanvas();
            var panel = DemoUiFactory.CreatePanel(
                "Chat Panel",
                canvas.transform,
                new Color(0.08f, 0.10f, 0.13f, 0.94f)
            );
            Place(panel, 0.67f, 0.08f, 0.98f, 0.92f);

            var title = DemoUiFactory.CreateText(
                "Title",
                panel.transform,
                panelTitle,
                26f,
                Color.white,
                TextAlignmentOptions.MidlineLeft
            );
            Place(title, 0.06f, 0.90f, 0.94f, 0.98f);

            var history = DemoUiFactory.CreateHistoryScroll(
                "History",
                panel.transform,
                out var historyText
            );
            Place(history, 0.05f, 0.22f, 0.95f, 0.88f);

            var input = DemoUiFactory.CreateInput(
                "Message Input",
                panel.transform,
                "Ask the avatar..."
            );
            Place(input, 0.05f, 0.06f, 0.72f, 0.16f);

            var sendButton = DemoUiFactory.CreateButton(
                "Send",
                panel.transform,
                "Send",
                new Color(0.08f, 0.48f, 0.50f)
            );
            Place(sendButton, 0.75f, 0.06f, 0.95f, 0.16f);

            GetComponent<ChatPanelController>().Bind(
                input,
                historyText,
                sendButton,
                history
            );
        }

        private Canvas CreateCanvas()
        {
            var item = new GameObject(
                "Demo Canvas",
                typeof(RectTransform),
                typeof(Canvas),
                typeof(CanvasScaler),
                typeof(GraphicRaycaster)
            );
            item.transform.SetParent(transform, false);

            var canvas = item.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 10;

            var scaler = item.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            return canvas;
        }

        private void EnsureEventSystem()
        {
            if (FindFirstObjectByType<EventSystem>() != null)
            {
                return;
            }

            var item = new GameObject(
                "EventSystem",
                typeof(EventSystem),
                typeof(StandaloneInputModule)
            );
            item.transform.SetParent(transform, false);
        }

        private static void Place(
            Component component,
            float minX,
            float minY,
            float maxX,
            float maxY
        )
        {
            DemoUiFactory.SetRect(
                (RectTransform)component.transform,
                new Vector2(minX, minY),
                new Vector2(maxX, maxY),
                Vector2.zero,
                Vector2.zero
            );
        }
    }
}
