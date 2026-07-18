import unittest

from app.services.ephemeral_agent_service import (
    detect_create_intent,
    detect_dismiss_intent,
    generate_agent_config,
    _display_name,
)


class EphemeralAgentServiceTests(unittest.TestCase):
    def test_detect_create_intent(self):
        self.assertEqual(detect_create_intent("act as a SQL expert"), "SQL expert")
        self.assertEqual(detect_create_intent("be my Python expert for this script"), "Python")
        self.assertEqual(detect_create_intent("create a debugging agent"), "debugging")
        self.assertEqual(detect_create_intent("help me debug this API"), "this API")
        self.assertIsNone(detect_create_intent("what is FastAPI?"))

    def test_detect_dismiss_intent(self):
        self.assertTrue(detect_dismiss_intent("dismiss agent"))
        self.assertTrue(detect_dismiss_intent("go back to normal"))
        self.assertFalse(detect_dismiss_intent("thanks for the help"))

    def test_generate_agent_config(self):
        config = generate_agent_config("SQL", "act as a SQL expert for this schema")
        self.assertIn("SQL", config["name"])
        self.assertIn("Ephemeral specialist agent", config["role_prompt"])
        self.assertIn("sql", config["role_prompt"].lower())

    def test_display_name(self):
        self.assertEqual(_display_name("SQL"), "SQL Expert")
        self.assertEqual(_display_name("API debugging specialist"), "API debugging specialist")


if __name__ == "__main__":
    unittest.main()
