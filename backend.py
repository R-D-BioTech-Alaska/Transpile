import os
from qiskit.providers.aer import AerSimulator
from qiskit.providers.backend import BackendV1
from qiskit.providers.aer.noise import NoiseModel, depolarizing_error, pauli_error

# Attempt IBMQ import; if unavailable, skip real-device backends
try:
    from qiskit_ibm_provider import IBMQ
except ImportError:
    IBMQ = None


class BackendManager:
    def __init__(self, ibm_api_token: str = None, ibm_hub: str = None, ibm_group: str = None, ibm_project: str = None):
        self.backends = {}
        self.noise_models = {}
        # Load Aer simulators
        self.backends["Aer (statevector)"] = AerSimulator(method='statevector')
        self.backends["Aer (qasm)"] = AerSimulator(method='qasm')
        # Attempt to load IBMQ backends if provider is available and token given
        if IBMQ and ibm_api_token:
            try:
                IBMQ.save_account(ibm_api_token, overwrite=True)
                IBMQ.load_account()
                provider = IBMQ.get_provider(hub=ibm_hub, group=ibm_group, project=ibm_project)
                for b in provider.backends():
                    if not b.configuration().simulator:
                        self.backends[f"IBM {b.name()}"] = b
            except Exception:
                # Silently ignore IBMQ errors
                pass
        # Default active backend
        self.active_backend = self.backends["Aer (statevector)"]

    def list_backends(self) -> list:
        return list(self.backends.keys())

    def set_backend(self, name: str) -> BackendV1:
        if name not in self.backends:
            raise ValueError(f"Backend '{name}' not available.")
        self.active_backend = self.backends[name]
        return self.active_backend

    def get_backend(self) -> BackendV1:
        return self.active_backend

    def create_noise_model(self, backend_name: str) -> NoiseModel:
        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not available.")
        backend = self.backends[backend_name]
        try:
            props = backend.properties()
            nm = NoiseModel.from_backend(props)
        except Exception:
            nm = NoiseModel()
        self.noise_models[backend_name] = nm
        return nm

    def get_noise_model(self, backend_name: str) -> NoiseModel:
        return self.noise_models.get(backend_name, NoiseModel())

    @staticmethod
    def sample_depolarizing(p: float) -> NoiseModel:
        err = depolarizing_error(p, 1)
        nm = NoiseModel()
        nm.add_all_qubit_quantum_error(err, ['u1', 'u2', 'u3'])
        return nm

    @staticmethod
    def sample_pauli(p: float) -> NoiseModel:
        err = pauli_error([('X', p), ('I', 1-p)])
        nm = NoiseModel()
        nm.add_all_qubit_quantum_error(err, ['cx'])
        return nm
