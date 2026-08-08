using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ResearchAvatarAgent.UI
{
    [RequireComponent(typeof(LlmSelectionController))]
    public sealed class LlmConfigPanelController : MonoBehaviour
    {
        [SerializeField]
        private TMP_Dropdown providerDropdown;

        [SerializeField]
        private TMP_Dropdown modelDropdown;

        [SerializeField]
        private TMP_Text statusText;

        [SerializeField]
        private TMP_InputField apiKeyInput;

        [SerializeField]
        private Button applyButton;

        private LlmSelectionController selection;

        public void Bind(
            TMP_Dropdown providers,
            TMP_Dropdown models,
            TMP_InputField apiKey,
            Button apply,
            TMP_Text status
        )
        {
            providerDropdown = providers;
            modelDropdown = models;
            apiKeyInput = apiKey;
            applyButton = apply;
            statusText = status;
        }

        private void Awake()
        {
            selection = GetComponent<LlmSelectionController>();
            if (providerDropdown == null ||
                modelDropdown == null ||
                apiKeyInput == null ||
                applyButton == null ||
                statusText == null)
            {
                Debug.LogError("LLM config panel UI references are incomplete.", this);
                enabled = false;
            }
        }

        private async void Start()
        {
            SetInteractive(false);
            statusText.SetText("Loading providers...");

            try
            {
                await selection.LoadProvidersAsync();
                PopulateProviders();
                providerDropdown.onValueChanged.AddListener(SelectProvider);
                modelDropdown.onValueChanged.AddListener(SelectModel);
                applyButton.onClick.AddListener(ApplyConfiguration);
                SetInteractive(true);
                statusText.SetText("Select a provider and model.");
            }
            catch (Exception error)
            {
                statusText.SetText($"Could not load providers: {error.Message}");
                Debug.LogException(error, this);
            }
        }

        private void OnDestroy()
        {
            providerDropdown?.onValueChanged.RemoveListener(SelectProvider);
            modelDropdown?.onValueChanged.RemoveListener(SelectModel);
            applyButton?.onClick.RemoveListener(ApplyConfiguration);
        }

        private void PopulateProviders()
        {
            var options = new List<string>();
            foreach (var provider in selection.Providers)
            {
                options.Add(provider.display_name);
            }

            providerDropdown.ClearOptions();
            providerDropdown.AddOptions(options);
            var selectedIndex = Array.FindIndex(
                selection.Providers,
                item => item == selection.SelectedProvider
            );
            providerDropdown.SetValueWithoutNotify(Mathf.Max(0, selectedIndex));
            SelectProvider(providerDropdown.value);
        }

        private void SelectProvider(int index)
        {
            if (index < 0 || index >= selection.Providers.Length)
            {
                return;
            }

            selection.SelectProvider(selection.Providers[index].provider);
            var options = new List<string>();
            foreach (var model in selection.SelectedProvider.models)
            {
                options.Add(model.display_name);
            }

            modelDropdown.ClearOptions();
            modelDropdown.AddOptions(options);
            var selectedIndex = Array.FindIndex(
                selection.SelectedProvider.models,
                item => item == selection.SelectedModel
            );
            modelDropdown.SetValueWithoutNotify(Mathf.Max(0, selectedIndex));
        }

        private void SelectModel(int index)
        {
            var models = selection.SelectedProvider.models;
            if (index >= 0 && index < models.Length)
            {
                selection.SelectModel(models[index].model);
            }
        }

        private async void ApplyConfiguration()
        {
            SetInteractive(false);
            statusText.SetText("Applying configuration...");

            try
            {
                var response = await selection.ApplyAsync(apiKeyInput.text);
                apiKeyInput.text = string.Empty;
                statusText.SetText($"Active: {response.provider} / {response.model}");
            }
            catch (Exception error)
            {
                statusText.SetText($"Configuration failed: {error.Message}");
                Debug.LogException(error, this);
            }
            finally
            {
                SetInteractive(true);
            }
        }

        private void SetInteractive(bool value)
        {
            providerDropdown.interactable = value;
            modelDropdown.interactable = value;
            apiKeyInput.interactable = value;
            applyButton.interactable = value;
        }
    }
}
