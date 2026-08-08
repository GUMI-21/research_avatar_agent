using UnityEngine;

namespace ResearchAvatarAgent.Scene
{
    public sealed class ClassroomEnvironment : MonoBehaviour
    {
        [SerializeField]
        private Transform avatarRoot;

        [SerializeField]
        private Camera sceneCamera;

        private Transform environmentRoot;

        private void Start()
        {
            // Runtime geometry uses local coordinates, so its root must be the world origin.
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
            BuildEnvironment();
            PositionPresentation();
        }

        private void BuildEnvironment()
        {
            // Runtime primitives keep the baseline scene reproducible without external assets.
            environmentRoot = new GameObject("Classroom").transform;
            environmentRoot.SetParent(transform, false);

            CreateBox(
                "Floor",
                new Vector3(0f, -0.05f, -1f),
                new Vector3(8f, 0.1f, 8f),
                new Color(0.48f, 0.52f, 0.55f)
            );
            CreateBox(
                "Back Wall",
                new Vector3(0f, 2.25f, 2.5f),
                new Vector3(8f, 4.5f, 0.1f),
                new Color(0.88f, 0.89f, 0.86f)
            );
            CreateBox(
                "Left Wall",
                new Vector3(-4f, 2.25f, -1f),
                new Vector3(0.1f, 4.5f, 7f),
                new Color(0.82f, 0.86f, 0.88f)
            );
            CreateBox(
                "Right Wall",
                new Vector3(4f, 2.25f, -1f),
                new Vector3(0.1f, 4.5f, 7f),
                new Color(0.82f, 0.86f, 0.88f)
            );
            CreateBox(
                "Blackboard",
                new Vector3(0f, 2.25f, 2.4f),
                new Vector3(4.8f, 2.2f, 0.12f),
                new Color(0.05f, 0.20f, 0.16f)
            );
            CreateBox(
                "Podium",
                new Vector3(0f, 0.55f, 0f),
                new Vector3(1.5f, 1.1f, 0.55f),
                new Color(0.42f, 0.25f, 0.14f)
            );

            RenderSettings.ambientLight = new Color(0.62f, 0.65f, 0.68f);
        }

        private void PositionPresentation()
        {
            // Unity uses +Z as forward; rotate the avatar to face the camera at -Z.
            if (avatarRoot != null)
            {
                avatarRoot.SetPositionAndRotation(
                    new Vector3(0f, 0f, 0.8f),
                    Quaternion.Euler(0f, 180f, 0f)
                );
            }
            else
            {
                Debug.LogWarning("Classroom requires an Avatar Root assignment.", this);
            }

            // Unity objects use an overloaded null check, which is not respected by ??=.
            if (sceneCamera == null)
            {
                sceneCamera = Camera.main;
            }
            if (sceneCamera == null)
            {
                sceneCamera = FindFirstObjectByType<Camera>();
            }
            if (sceneCamera == null)
            {
                Debug.LogWarning("Classroom requires a scene camera.", this);
                return;
            }

            sceneCamera.transform.position = new Vector3(0f, 1.65f, -5.5f);
            // Frame the avatar's upper body, podium, and blackboard in one view.
            sceneCamera.transform.LookAt(new Vector3(0f, 1.35f, 0.8f));
            sceneCamera.fieldOfView = 42f;
            sceneCamera.backgroundColor = new Color(0.78f, 0.84f, 0.88f);
        }

        private void CreateBox(
            string objectName,
            Vector3 position,
            Vector3 scale,
            Color color
        )
        {
            var item = GameObject.CreatePrimitive(PrimitiveType.Cube);
            item.name = objectName;
            item.transform.SetParent(environmentRoot, false);
            item.transform.localPosition = position;
            item.transform.localScale = scale;

            var shader = Shader.Find("Universal Render Pipeline/Lit") ??
                         Shader.Find("Standard");
            item.GetComponent<Renderer>().material = new Material(shader)
            {
                color = color,
            };
        }
    }
}
