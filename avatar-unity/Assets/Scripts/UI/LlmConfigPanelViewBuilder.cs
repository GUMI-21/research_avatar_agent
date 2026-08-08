using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    [DefaultExecutionOrder(-90)]
    [RequireComponent(typeof(ChatPanelViewBuilder))]
    [RequireComponent(typeof(LlmConfigPanelController))]
    public sealed class LlmConfigPanelViewBuilder : MonoBehaviour
    {
        private void Awake()
        {
            var canvas = GetComponentInChildren<Canvas>();
            if (canvas == null)
            {
                Debug.LogError("LLM config panel requires the demo Canvas.", this);
                enabled = false;
                return;
            }

            var panel = DemoUiFactory.CreatePanel(
                "LLM Config Panel",
                canvas.transform,
                new Color(0.08f, 0.10f, 0.13f, 0.94f)
            );
            Place(panel, 0.02f, 0.48f, 0.32f, 0.92f);

            var title = DemoUiFactory.CreateText(
                "Title",
                panel.transform,
                "LLM Settings",
                24f,
                Color.white,
                TextAlignmentOptions.MidlineLeft
            );
            Place(title, 0.06f, 0.86f, 0.94f, 0.96f);

            CreateLabel(panel.transform, "Provider", 0.74f, 0.82f);
            var providers = DemoUiFactory.CreateDropdown(
                "Provider",
                panel.transform
            );
            Place(providers, 0.06f, 0.61f, 0.94f, 0.73f);

            CreateLabel(panel.transform, "Model", 0.49f, 0.57f);
            var models = DemoUiFactory.CreateDropdown("Model", panel.transform);
            Place(models, 0.06f, 0.36f, 0.94f, 0.48f);

            CreateLabel(panel.transform, "API Key", 0.24f, 0.32f);
            var apiKey = DemoUiFactory.CreateInput(
                "API Key",
                panel.transform,
                "Enter API key"
            );
            apiKey.contentType = TMP_InputField.ContentType.Password;
            apiKey.ForceLabelUpdate();
            Place(apiKey, 0.06f, 0.11f, 0.94f, 0.23f);

            var status = DemoUiFactory.CreateText(
                "Status",
                panel.transform,
                "Loading providers...",
                14f,
                new Color(0.78f, 0.82f, 0.86f),
                TextAlignmentOptions.MidlineLeft
            );
            Place(status, 0.06f, 0.02f, 0.66f, 0.10f);

            var apply = DemoUiFactory.CreateButton(
                "Apply",
                panel.transform,
                "Apply",
                new Color(0.08f, 0.48f, 0.50f)
            );
            Place(apply, 0.70f, 0.02f, 0.94f, 0.10f);

            GetComponent<LlmConfigPanelController>().Bind(
                providers,
                models,
                apiKey,
                apply,
                status
            );
        }

        private static void CreateLabel(
            Transform parent,
            string value,
            float minY,
            float maxY
        )
        {
            var label = DemoUiFactory.CreateText(
                $"{value} Label",
                parent,
                value,
                15f,
                new Color(0.82f, 0.85f, 0.88f)
            );
            Place(label, 0.06f, minY, 0.94f, maxY);
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
