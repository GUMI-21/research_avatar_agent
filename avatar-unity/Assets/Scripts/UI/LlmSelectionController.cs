using System;
using System.Threading.Tasks;
using ResearchAvatarAgent.Api;
using UnityEngine;

namespace ResearchAvatarAgent.UI
{
    [RequireComponent(typeof(LlmConfigClient))]
    public sealed class LlmSelectionController : MonoBehaviour
    {
        [SerializeField]
        private string initialProvider = LlmProviderIds.Mock;

        private LlmConfigClient configClient;

        public LlmProviderOption[] Providers { get; private set; } =
            Array.Empty<LlmProviderOption>();

        public LlmProviderOption SelectedProvider { get; private set; }
        public LlmModelOption SelectedModel { get; private set; }

        private void Awake()
        {
            configClient = GetComponent<LlmConfigClient>();
        }

        public async Task LoadProvidersAsync()
        {
            var response = await configClient.GetProvidersAsync();
            Providers = response.providers;

            if (!SelectProvider(initialProvider) && Providers.Length > 0)
            {
                SelectProvider(Providers[0].provider);
            }
        }

        public bool SelectProvider(string providerId)
        {
            var provider = Array.Find(
                Providers,
                item => item.provider == providerId
            );
            if (provider == null)
            {
                return false;
            }

            SelectedProvider = provider;
            SelectedModel = Array.Find(
                provider.models,
                item => item.model == provider.default_model
            );
            if (SelectedModel == null && provider.models.Length > 0)
            {
                SelectedModel = provider.models[0];
            }

            return true;
        }

        public bool SelectModel(string modelId)
        {
            if (SelectedProvider == null)
            {
                return false;
            }

            var model = Array.Find(
                SelectedProvider.models,
                item => item.model == modelId
            );
            if (model == null)
            {
                return false;
            }

            SelectedModel = model;
            return true;
        }

        public async Task<LlmConfigResponse> ApplyAsync(string apiKey = null)
        {
            if (SelectedProvider == null || SelectedModel == null)
            {
                throw new InvalidOperationException(
                    "Load and select an LLM provider before applying configuration."
                );
            }

            var request = new LlmConfigRequest(
                SelectedProvider.provider,
                SelectedModel.model,
                string.IsNullOrWhiteSpace(apiKey) ? null : apiKey
            );
            return await configClient.ConfigureAsync(request);
        }
    }
}
