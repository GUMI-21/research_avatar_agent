using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    internal static partial class DemoUiFactory
    {
        public static TMP_InputField CreateInput(
            string name,
            Transform parent,
            string placeholderValue
        )
        {
            var background = CreatePanel(
                name,
                parent,
                new Color(0.96f, 0.97f, 0.98f)
            );
            var input = background.gameObject.AddComponent<TMP_InputField>();
            input.targetGraphic = background;

            // The viewport clips text that extends beyond the input field.
            var viewport = CreateRect("Viewport", input.transform);
            viewport.gameObject.AddComponent<RectMask2D>();
            SetRect(
                viewport,
                Vector2.zero,
                Vector2.one,
                new Vector2(14f, 8f),
                new Vector2(-14f, -8f)
            );

            var text = CreateText(
                "Text",
                viewport,
                string.Empty,
                18f,
                new Color(0.10f, 0.12f, 0.15f),
                TextAlignmentOptions.MidlineLeft
            );
            SetRect(text.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);

            var placeholder = CreateText(
                "Placeholder",
                viewport,
                placeholderValue,
                18f,
                new Color(0.45f, 0.49f, 0.54f),
                TextAlignmentOptions.MidlineLeft
            );
            placeholder.fontStyle = FontStyles.Italic;
            SetRect(
                placeholder.rectTransform,
                Vector2.zero,
                Vector2.one,
                Vector2.zero,
                Vector2.zero
            );

            input.textViewport = viewport;
            input.textComponent = text;
            input.placeholder = placeholder;
            input.lineType = TMP_InputField.LineType.SingleLine;
            input.characterLimit = 4000;
            return input;
        }

        public static ScrollRect CreateHistoryScroll(
            string name,
            Transform parent,
            out TMP_Text historyText
        )
        {
            var background = CreatePanel(
                name,
                parent,
                new Color(0.97f, 0.98f, 0.99f, 0.96f)
            );
            var scroll = background.gameObject.AddComponent<ScrollRect>();

            var viewport = CreateRect("Viewport", scroll.transform);
            viewport.gameObject.AddComponent<RectMask2D>();
            SetRect(
                viewport,
                Vector2.zero,
                Vector2.one,
                new Vector2(14f, 14f),
                new Vector2(-14f, -14f)
            );

            var content = CreateText(
                "History",
                viewport,
                string.Empty,
                17f,
                new Color(0.12f, 0.15f, 0.18f)
            );
            content.rectTransform.anchorMin = new Vector2(0f, 1f);
            content.rectTransform.anchorMax = Vector2.one;
            content.rectTransform.pivot = new Vector2(0.5f, 1f);
            content.rectTransform.sizeDelta = Vector2.zero;
            content.gameObject.AddComponent<ContentSizeFitter>().verticalFit =
                ContentSizeFitter.FitMode.PreferredSize;

            scroll.viewport = viewport;
            scroll.content = content.rectTransform;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 24f;
            historyText = content;
            return scroll;
        }
    }
}
