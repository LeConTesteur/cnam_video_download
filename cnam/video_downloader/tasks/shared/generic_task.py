"""
Définie les fonctions principales à la génération des tâches.
"""
from functools import wraps
from doit.task import Task, DelayedLoader


class GenericTask:
    """
    Classe abstraite définissant les fonctions principales à la génération des tâches.
    """

    def model_post_init(self, *_, **__):
        """
        Initialisation appelée par pydantic
        """
        # pylint: disable=attribute-defined-outside-init
        self._main_task = Task(name=self.main_task_name, actions=[], has_subtask=True)
        self._sub_init()

    @property
    def main_task_name(self):
        """
        Retourne le nom de la tâche principal du générateur.
        """
        if hasattr(self, "id"):
            return f"{self.__class__.__name__}_{self.id}"
        return self.__class__.__name__

    @property
    def main_task(self):
        """
        Retourne la tâche parente des sous-taches.
        """
        return self._main_task

    def _sub_init(self):
        pass

    def to_tasks(self):
        """
        Méthode servant à générer les tâches. Doit retourner les tâches via un yield. Ne pas oublier
        la tâche principale.
        """
        raise NotImplementedError()

    @wraps(DelayedLoader)
    def to_delayed_tasks(self, executed=None, target_regex=None, creates=None):
        """
        Converti les tâches du générateur en tâche à retardement. Ceele-ci attend l'exécution
        d'une autre tâche pour se définir.
        """
        new_main = Task(
            name=self.main_task.name,
            actions=None,
            loader=DelayedLoader(
                self.to_tasks,
                executed=executed,
                target_regex=target_regex,
                creates=creates,
            ),
            doc=self.main_task.doc,
        )
        # pylint: disable=attribute-defined-outside-init
        self._main_task = new_main
        yield self.main_task

    @wraps(Task)
    def new_sub_task(self, *args, **kwargs) -> Task:
        """
        Créer une sous-tâche à la tâche principale.
        """
        if "subtask_of" not in kwargs:
            kwargs.update({"subtask_of": self.main_task.name})
        task = Task(*args, **kwargs)
        self.main_task.task_dep.append(task.name)
        return task
