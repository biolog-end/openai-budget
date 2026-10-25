import os
import tempfile
import unittest

_tmp = tempfile.TemporaryDirectory()
os.environ['OPENAI_BUDGET_DIR'] = _tmp.name

import openai_budget as ob


class CatalogTests(unittest.TestCase):
    def test_groups_follow_account_offer(self):
        self.assertEqual(ob.group_for('gpt-5.4'), 'large')
        self.assertEqual(ob.group_for('o4-mini-2025-04-16'), 'small')
        self.assertIsNone(ob.group_for('gpt-5.5'))
        self.assertIsNone(ob.group_for('gpt-5.6-luna'))

    def test_models_rows(self):
        rows = {row['id']: row for row in ob.models()}
        self.assertEqual(rows['gpt-5.4-mini']['free_group'], 'small')
        self.assertEqual(rows['gpt-5.4-mini']['price']['cached_input'], .075)
        self.assertIsNone(rows['gpt-6-astra']['free_group'])

    def test_capabilities(self):
        self.assertTrue(ob.supports_reasoning('gpt-7-new'))
        self.assertFalse(ob.supports_reasoning('gpt-4.1-mini'))
        self.assertEqual(ob.reasoning_off('gpt-5'), 'minimal')
        self.assertEqual(ob.reasoning_off('gpt-5.4'), 'none')
        self.assertIsNone(ob.reasoning_off('gpt-5.4-pro'))
        self.assertEqual(ob.temperature_mode('gpt-4o'), 'always')
        self.assertEqual(ob.temperature_mode('gpt-5.2'), 'without_reasoning')
        self.assertIsNone(ob.temperature_mode('gpt-5-mini'))

    def test_text_models(self):
        self.assertTrue(ob.is_text_model('gpt-5.4-mini'))
        self.assertTrue(ob.is_text_model('gpt-5.5-pro'))
        for name in ('gpt-4o-audio-preview', 'gpt-4.1-2025-04-14', 'gpt-image-1', 'text-embedding-3-small',
                     'gpt-5-chat-latest', 'gpt-9-pro'):
            self.assertFalse(ob.is_text_model(name), name)


if __name__ == '__main__':
    unittest.main()
