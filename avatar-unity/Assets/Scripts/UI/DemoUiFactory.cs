using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    internal static class DemoUiFactory
    {
        public static RectTransform CreateRect(string name, Transform parent)
        {
            var item = new GameObject(name, typeof(RectTransform));
            var rect = item.GetComponent<RectTransform>();
            rect.SetParent(parent, false);
            rect.localScale = Vector3.one;
            return rect;
        }

        public static void SetRect(
            RectTransform rect,
            Vector2 anchorMin,
            Vector2 anchorMax,
            Vector2 offsetMin,
            Vector2 offsetMax
        )
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
        }

        public static Image CreatePanel(
            string name,
            Transform parent,
            Color color
        )
        {
            var image = CreateRect(name, parent).gameObject.AddComponent<Image>();
            image.color = color;
            return image;
        }

        public static TextMeshProUGUI CreateText(
            string name,
            Transform parent,
            string value,
            float fontSize,
            Color color,
            TextAlignmentOptions alignment = TextAlignmentOptions.Left
        )
        {
            var text = CreateRect(name, parent)
                .gameObject.AddComponent<TextMeshProUGUI>();
            text.text = value;
            text.font = TMP_Settings.defaultFontAsset;
            text.fontSize = fontSize;
            text.color = color;
            text.alignment = alignment;
            text.textWrappingMode = TextWrappingModes.Normal;
            text.raycastTarget = false;
            return text;
        }

        public static Button CreateButton(
            string name,
            Transform parent,
            string label,
            Color backgroundColor
        )
        {
            var image = CreatePanel(name, parent, backgroundColor);
            var button = image.gameObject.AddComponent<Button>();
            button.targetGraphic = image;

            var colors = button.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(0.90f, 0.94f, 1f);
            colors.pressedColor = new Color(0.78f, 0.85f, 0.94f);
            button.colors = colors;

            var text = CreateText(
                "Label",
                button.transform,
                label,
                18f,
                Color.white,
                TextAlignmentOptions.Center
            );
            SetRect(
                text.rectTransform,
                Vector2.zero,
                Vector2.one,
                Vector2.zero,
                Vector2.zero
            );
            return button;
        }

    }
}
