import unittest

from app.services.build_mode_service import (
    extract_project_files,
    is_build_request,
    parse_fence_info,
)


class BuildModeServiceTests(unittest.TestCase):
    def test_is_build_request_positive(self):
        self.assertTrue(is_build_request("build me a todo app"))
        self.assertTrue(is_build_request("create a full stack chatbot project"))
        self.assertTrue(is_build_request("scaffold a FastAPI backend"))
        self.assertTrue(is_build_request("build this project"))

    def test_is_build_request_negative(self):
        self.assertFalse(is_build_request("what is FastAPI?"))
        self.assertFalse(is_build_request("explain how React hooks work"))
        self.assertFalse(is_build_request(""))

    def test_parse_fence_info_with_path(self):
        lang, path = parse_fence_info("typescript:src/App.tsx")
        self.assertEqual(path, "src/App.tsx")
        self.assertEqual(lang, "typescript")

    def test_extract_project_files(self):
        md = """
```typescript:src/App.tsx
export default function App() { return null }
```

```json:package.json
{"name": "demo"}
```
"""
        files = extract_project_files(md)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["path"], "src/App.tsx")


if __name__ == "__main__":
    unittest.main()
