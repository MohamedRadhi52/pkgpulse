import pytest

from pkgpulse.ingest.bronze import Partition
from pkgpulse.ingest.junction import should_write

ARCHIVE = Partition("archive", "a1")
DUMP = Partition("dump", "d1")


@pytest.mark.parametrize(
    ("existing", "candidate", "expected"),
    [
        pytest.param(None, ARCHIVE, True, id="nouveau-jour-archive"),
        pytest.param(None, DUMP, True, id="nouveau-jour-dump"),
        pytest.param(DUMP, ARCHIVE, True, id="archive-remplace-dump"),
        pytest.param(ARCHIVE, DUMP, False, id="dump-ne-remplace-pas-archive"),
        pytest.param(DUMP, Partition("dump", "d2"), True, id="donnees-tardives"),
        pytest.param(DUMP, DUMP, False, id="dump-inchange"),
        pytest.param(ARCHIVE, ARCHIVE, False, id="archive-inchangee"),
    ],
)
def test_junction_rule(existing, candidate, expected):
    assert should_write(existing, candidate) is expected
