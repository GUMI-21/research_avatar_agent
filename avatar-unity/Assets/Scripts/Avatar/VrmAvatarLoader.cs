using System;
using System.IO;
using System.Threading;
using UniVRM10;
using UnityEngine;

namespace ResearchAvatarAgent.Avatar
{
    public sealed class VrmAvatarLoader : MonoBehaviour
    {
        [SerializeField]
        [Tooltip("VRM file name under Assets/Models.")]
        private string modelFileName = "male1.vrm";

        private CancellationTokenSource _destroyCancellation;

        public Vrm10Instance Instance { get; private set; }

        private async void Start()
        {
            var fileName = Path.GetFileName(modelFileName);
            if (string.IsNullOrWhiteSpace(fileName) ||
                !fileName.EndsWith(".vrm", StringComparison.OrdinalIgnoreCase))
            {
                Debug.LogError("Avatar model must be a .vrm file name.", this);
                return;
            }

            var modelPath = Path.Combine(Application.dataPath, "Models", fileName);
            if (!File.Exists(modelPath))
            {
                Debug.LogError($"Avatar model was not found: {modelPath}", this);
                return;
            }

            _destroyCancellation = new CancellationTokenSource();

            try
            {
                Instance = await Vrm10.LoadPathAsync(
                    modelPath,
                    controlRigGenerationOption: ControlRigGenerationOption.None,
                    ct: _destroyCancellation.Token
                );

                if (Instance == null)
                {
                    Debug.LogError($"UniVRM could not load: {modelPath}", this);
                    return;
                }

                Instance.transform.SetParent(transform, false);
                Debug.Log($"Loaded avatar model: {fileName}", this);
            }
            catch (OperationCanceledException)
            {
                // The scene or loader was destroyed while the model was loading.
            }
            catch (Exception error)
            {
                Debug.LogException(error, this);
            }
        }

        private void OnDestroy()
        {
            _destroyCancellation?.Cancel();
            _destroyCancellation?.Dispose();
        }
    }
}
