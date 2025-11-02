"""Unit tests for pattern detection in code analyzer.

Tests the enhanced pattern detection system including:
- Design patterns (Factory, Singleton, Observer, Strategy, etc.)
- CRUD operations
- Common patterns (validation, serialization, etc.)
- Anti-patterns (God class, long method, high complexity, etc.)
"""

import textwrap

import pytest

from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.models import CodeElement, CodeElementType
from docpilot.core.parser import PythonParser


@pytest.fixture
def analyzer():
    """Create a code analyzer with pattern detection enabled."""
    return CodeAnalyzer(
        calculate_complexity=True,
        infer_types=True,
        detect_patterns=True,
    )


@pytest.fixture
def parser():
    """Create a Python parser."""
    return PythonParser()


class TestDesignPatterns:
    """Test detection of design patterns."""

    def test_singleton_pattern(self, analyzer):
        """Test detection of Singleton pattern."""
        code = textwrap.dedent("""
            class DatabaseConnection:
                _instance = None

                def __new__(cls):
                    if cls._instance is None:
                        cls._instance = super().__new__(cls)
                    return cls._instance

                def connect(self):
                    pass
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "singleton" in element.detected_patterns
        assert element.pattern_confidence > 0.0

    def test_factory_pattern_class(self, analyzer):
        """Test detection of Factory pattern in class."""
        code = textwrap.dedent("""
            class UserFactory:
                def create_user(self, user_type):
                    if user_type == "admin":
                        return AdminUser()
                    return RegularUser()
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "factory" in element.detected_patterns

    def test_factory_method_pattern(self, analyzer):
        """Test detection of Factory Method pattern."""
        code = textwrap.dedent("""
            def create_user(name: str, email: str):
                return User(name=name, email=email)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "crud_create" in element.detected_patterns or "factory_method" in element.detected_patterns

    def test_observer_pattern(self, analyzer):
        """Test detection of Observer pattern."""
        code = textwrap.dedent("""
            class EventManager:
                def __init__(self):
                    self.listeners = []

                def subscribe(self, listener):
                    self.listeners.append(listener)

                def notify(self, event):
                    for listener in self.listeners:
                        listener.update(event)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "observer" in element.detected_patterns

    def test_strategy_pattern(self, analyzer):
        """Test detection of Strategy pattern."""
        code = textwrap.dedent("""
            class SortingStrategy:
                def sort(self, data):
                    raise NotImplementedError

            class QuickSortStrategy(SortingStrategy):
                def sort(self, data):
                    return sorted(data)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)

        for element in result.elements:
            analyzer.analyze_element(element)

        # Check if strategy pattern detected in any element
        patterns = []
        for elem in result.elements:
            patterns.extend(elem.detected_patterns)

        assert "strategy" in patterns

    def test_adapter_pattern(self, analyzer):
        """Test detection of Adapter pattern."""
        code = textwrap.dedent("""
            class DatabaseAdapter:
                def __init__(self, database):
                    self.database = database

                def query(self, sql):
                    return self.database.execute(sql)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "adapter" in element.detected_patterns

    def test_command_pattern(self, analyzer):
        """Test detection of Command pattern."""
        code = textwrap.dedent("""
            class EmailCommand:
                def __init__(self, recipient, message):
                    self.recipient = recipient
                    self.message = message

                def execute(self):
                    send_email(self.recipient, self.message)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "command" in element.detected_patterns


class TestCRUDPatterns:
    """Test detection of CRUD operation patterns."""

    def test_crud_create(self, analyzer):
        """Test detection of CREATE operation."""
        code = textwrap.dedent("""
            def create_user(name: str, email: str) -> User:
                user = User(name=name, email=email)
                db.session.add(user)
                db.session.commit()
                return user
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "crud_create" in element.detected_patterns
        # Should have suggestions for CRUD create
        assert any("CRUD create" in s for s in element.suggestions)

    def test_crud_read(self, analyzer):
        """Test detection of READ operation."""
        code = textwrap.dedent("""
            def get_user(user_id: int) -> User:
                return db.session.query(User).filter_by(id=user_id).first()
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "crud_read" in element.detected_patterns

    def test_crud_update(self, analyzer):
        """Test detection of UPDATE operation."""
        code = textwrap.dedent("""
            def update_user(user_id: int, name: str) -> User:
                user = User.query.get(user_id)
                user.name = name
                db.session.commit()
                return user
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "crud_update" in element.detected_patterns

    def test_crud_delete(self, analyzer):
        """Test detection of DELETE operation."""
        code = textwrap.dedent("""
            def delete_user(user_id: int) -> None:
                user = User.query.get(user_id)
                db.session.delete(user)
                db.session.commit()
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "crud_delete" in element.detected_patterns


class TestCommonPatterns:
    """Test detection of common code patterns."""

    def test_validation_pattern(self, analyzer):
        """Test detection of validation pattern."""
        code = textwrap.dedent("""
            def validate_email(email: str) -> bool:
                import re
                pattern = r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'
                return bool(re.match(pattern, email))
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "validation" in element.detected_patterns

    def test_serialization_pattern(self, analyzer):
        """Test detection of serialization pattern."""
        code = textwrap.dedent("""
            def serialize_user(user: User) -> dict:
                return {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email
                }
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "serialization" in element.detected_patterns

    def test_parser_pattern(self, analyzer):
        """Test detection of parser pattern."""
        code = textwrap.dedent("""
            def parse_json(json_string: str) -> dict:
                import json
                return json.loads(json_string)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "parser" in element.detected_patterns

    def test_formatter_pattern(self, analyzer):
        """Test detection of formatter pattern."""
        code = textwrap.dedent("""
            def format_date(date: datetime) -> str:
                return date.strftime('%Y-%m-%d')
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "formatter" in element.detected_patterns

    def test_predicate_pattern(self, analyzer):
        """Test detection of predicate pattern."""
        code = textwrap.dedent("""
            def is_valid_user(user: User) -> bool:
                return user.email is not None and user.name is not None
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "predicate" in element.detected_patterns


class TestAntiPatterns:
    """Test detection of anti-patterns."""

    def test_god_class_antipattern(self, analyzer):
        """Test detection of God Class anti-pattern."""
        # Create a class with many methods
        methods = "\n    ".join([f"def method_{i}(self): pass" for i in range(25)])
        code = f"""
class GodClass:
    {methods}
        """

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "anti_pattern_god_class" in element.detected_patterns
        assert any("Single Responsibility" in s for s in element.suggestions)

    def test_long_method_antipattern(self, analyzer):
        """Test detection of Long Method anti-pattern."""
        # Create a method with many lines
        lines = "\n    ".join([f"x = {i}" for i in range(105)])
        code = f"""
def long_method():
    {lines}
    return x
        """

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "anti_pattern_long_method" in element.detected_patterns
        assert any("refactoring" in s.lower() for s in element.suggestions)

    def test_high_complexity_antipattern(self, analyzer):
        """Test detection of High Complexity anti-pattern."""
        code = textwrap.dedent("""
            def complex_method(a, b, c, d, e):
                if a > 0:
                    if b > 0:
                        if c > 0:
                            if d > 0:
                                if e > 0:
                                    for i in range(10):
                                        if i % 2 == 0:
                                            for j in range(10):
                                                if j % 2 == 0:
                                                    while True:
                                                        if a == b:
                                                            return True
                                                        break
                return False
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert element.complexity_score and element.complexity_score > 15
        assert "anti_pattern_high_complexity" in element.detected_patterns
        assert any("complexity" in s.lower() for s in element.suggestions)

    def test_too_many_parameters_antipattern(self, analyzer):
        """Test detection of Too Many Parameters anti-pattern."""
        code = textwrap.dedent("""
            def method_with_many_params(
                param1, param2, param3, param4, param5, param6, param7
            ):
                pass
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "anti_pattern_too_many_parameters" in element.detected_patterns
        assert any("parameters" in s.lower() for s in element.suggestions)

    def test_magic_numbers_antipattern(self, analyzer):
        """Test detection of Magic Numbers anti-pattern."""
        code = textwrap.dedent("""
            def calculate_discount(price):
                if price > 100:
                    return price * 0.9
                elif price > 50:
                    return price * 0.95
                elif price > 25:
                    return price * 0.97
                else:
                    return price * 0.99
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "anti_pattern_magic_numbers" in element.detected_patterns
        assert any("constants" in s.lower() for s in element.suggestions)


class TestPatternConfidence:
    """Test pattern confidence calculation."""

    def test_confidence_with_design_patterns(self, analyzer):
        """Test that design patterns increase confidence."""
        code = textwrap.dedent("""
            class UserFactory:
                @staticmethod
                def create_user(user_type):
                    return User(user_type)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert element.pattern_confidence > 0.5

    def test_confidence_penalty_with_antipatterns(self, analyzer):
        """Test that anti-patterns reduce confidence."""
        # Create class with anti-patterns
        methods = "\n    ".join([f"def method_{i}(self): pass" for i in range(25)])
        code = f"""
class BadClass:
    {methods}
        """

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        # Should detect patterns but with lower confidence due to anti-pattern
        assert "anti_pattern_god_class" in element.detected_patterns
        # Confidence should be reduced
        assert element.pattern_confidence < 0.9


class TestSuggestions:
    """Test generation of improvement suggestions."""

    def test_suggestions_for_untyped_parameters(self, analyzer):
        """Test suggestions for missing type hints."""
        code = textwrap.dedent("""
            def process_data(data, config, options):
                return data
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert any("type hints" in s.lower() for s in element.suggestions)

    def test_suggestions_for_factory_method(self, analyzer):
        """Test suggestions for factory methods."""
        code = textwrap.dedent("""
            def create_connection(db_type: str):
                if db_type == "postgres":
                    return PostgresConnection()
                return MySQLConnection()
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        # Should have factory-related suggestions
        if "factory_method" in element.detected_patterns or "crud_create" in element.detected_patterns:
            assert element.suggestions  # Should have some suggestions

    def test_suggestions_for_singleton(self, analyzer):
        """Test suggestions for singleton pattern."""
        code = textwrap.dedent("""
            class Config:
                _instance = None

                def __new__(cls):
                    if cls._instance is None:
                        cls._instance = super().__new__(cls)
                    return cls._instance
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        if "singleton" in element.detected_patterns:
            assert any("thread" in s.lower() for s in element.suggestions)


class TestPatternMetadata:
    """Test that pattern metadata is correctly stored."""

    def test_patterns_stored_in_detected_patterns(self, analyzer):
        """Test patterns are stored in detected_patterns field."""
        code = textwrap.dedent("""
            def validate_email(email: str) -> bool:
                return "@" in email
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert isinstance(element.detected_patterns, list)
        assert len(element.detected_patterns) > 0

    def test_patterns_also_in_metadata(self, analyzer):
        """Test patterns are also stored in metadata for backward compatibility."""
        code = textwrap.dedent("""
            def get_user(user_id: int):
                return User.query.get(user_id)
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert "patterns" in element.metadata
        assert element.metadata["patterns"] == element.detected_patterns

    def test_suggestions_stored(self, analyzer):
        """Test suggestions are stored in suggestions field."""
        code = textwrap.dedent("""
            def func(a, b, c, d, e, f, g):
                pass
        """)

        parser = PythonParser()
        result = parser.parse_string(code)
        element = result.elements[0]

        analyzer.analyze_element(element)

        assert isinstance(element.suggestions, list)
        if "anti_pattern_too_many_parameters" in element.detected_patterns:
            assert len(element.suggestions) > 0
