from typing import List, Dict


def get_start_index_and_length_for_words_from_text(
        text: str,
        words: List[str]
) -> List[Dict]:
    result = []
    start_pos = 0

    for word in words:
        # Find the word starting from the current search position
        index = text.find(word, start_pos)
        if index == -1:
            raise ValueError(f"Word '{word}' not found in text starting from index {start_pos}")

        result.append({
            "word": word,
            "index": index,
            "length": len(word)
        })

        # Move search start beyond this word to avoid matching earlier occurrences again
        start_pos = index + len(word)

    return result
