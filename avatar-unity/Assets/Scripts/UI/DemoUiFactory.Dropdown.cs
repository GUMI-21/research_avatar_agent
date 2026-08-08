using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    internal static partial class DemoUiFactory
    {
        public static TMP_Dropdown CreateDropdown(
            string name,
            Transform parent
        )
        {
            var background = CreatePanel(
                name,
                parent,
                new Color(0.96f, 0.97f, 0.98f)
            );
            var dropdown = background.gameObject.AddComponent<TMP_Dropdown>();
            dropdown.targetGraphic = background;

            var caption = CreateText(
                "Label",
                dropdown.transform,
                string.Empty,
                17f,
                new Color(0.10f, 0.12f, 0.15f),
                TextAlignmentOptions.MidlineLeft
            );
            SetRect(
                caption.rectTransform,
                Vector2.zero,
                Vector2.one,
                new Vector2(12f, 5f),
                new Vector2(-38f, -5f)
            );

            var arrow = CreateText(
                "Arrow",
                dropdown.transform,
                "v",
                16f,
                new Color(0.30f, 0.34f, 0.38f),
                TextAlignmentOptions.Center
            );
            SetRect(
                arrow.rectTransform,
                new Vector2(1f, 0f),
                Vector2.one,
                new Vector2(-34f, 4f),
                new Vector2(-8f, -4f)
            );

            var template = CreatePanel(
                "Template",
                dropdown.transform,
                new Color(0.94f, 0.96f, 0.98f)
            );
            var templateRect = template.rectTransform;
            templateRect.anchorMin = Vector2.zero;
            templateRect.anchorMax = new Vector2(1f, 0f);
            templateRect.pivot = new Vector2(0.5f, 1f);
            templateRect.anchoredPosition = new Vector2(0f, -4f);
            templateRect.sizeDelta = new Vector2(0f, 180f);

            var scroll = template.gameObject.AddComponent<ScrollRect>();
            var viewport = CreateRect("Viewport", template.transform);
            viewport.gameObject.AddComponent<RectMask2D>();
            SetRect(
                viewport,
                Vector2.zero,
                Vector2.one,
                new Vector2(4f, 4f),
                new Vector2(-4f, -4f)
            );

            var content = CreateRect("Content", viewport);
            content.anchorMin = new Vector2(0f, 1f);
            content.anchorMax = Vector2.one;
            content.pivot = new Vector2(0.5f, 1f);
            content.sizeDelta = new Vector2(0f, 36f);

            var itemImage = CreatePanel(
                "Item",
                content,
                new Color(0.94f, 0.96f, 0.98f)
            );
            itemImage.rectTransform.anchorMin = new Vector2(0f, 0.5f);
            itemImage.rectTransform.anchorMax = new Vector2(1f, 0.5f);
            itemImage.rectTransform.sizeDelta = new Vector2(0f, 36f);

            var toggle = itemImage.gameObject.AddComponent<Toggle>();
            toggle.targetGraphic = itemImage;
            var itemLabel = CreateText(
                "Item Label",
                toggle.transform,
                "Option",
                16f,
                new Color(0.10f, 0.12f, 0.15f),
                TextAlignmentOptions.MidlineLeft
            );
            SetRect(
                itemLabel.rectTransform,
                Vector2.zero,
                Vector2.one,
                new Vector2(12f, 3f),
                new Vector2(-8f, -3f)
            );

            scroll.viewport = viewport;
            scroll.content = content;
            scroll.horizontal = false;
            scroll.movementType = ScrollRect.MovementType.Clamped;

            dropdown.template = templateRect;
            dropdown.captionText = caption;
            dropdown.itemText = itemLabel;
            template.gameObject.SetActive(false);
            return dropdown;
        }
    }
}
