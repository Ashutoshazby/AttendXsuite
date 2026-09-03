# Oracle Face API Deployment

Use this when Hugging Face ZeroGPU quota is blocking face registration or scan.

## Free VM

Oracle's current Always Free Ampere A1 allowance is 2 OCPUs and 12 GB RAM across Ampere A1 VMs. Create one Ubuntu Ampere A1 VM with 2 OCPUs and 12 GB RAM if capacity is available.

## OCI Console

1. Create a compute instance.
2. Image: Ubuntu.
3. Shape: `VM.Standard.A1.Flex`, Always Free eligible.
4. OCPU: `2`.
5. Memory: `12 GB`.
6. Save/download the SSH private key.
7. Open ingress TCP port `7860` in the VM subnet security list or NSG.

Ubuntu also has a host firewall. The install script runs `ufw allow 7860/tcp`, but OCI ingress must also be open.

## VM Install

SSH into the VM:

```bash
ssh -i path/to/private.key ubuntu@PUBLIC_IP
```

Run:

```bash
export HF_FACE_API_TOKEN='same-secret-used-by-render'
curl -fsSL https://raw.githubusercontent.com/Ashutoshazby/AttendXsuite/main/deploy/oracle/install_face_api.sh | bash
```

Check:

```bash
curl http://PUBLIC_IP:7860/health
sudo journalctl -u attendxsuite-face-api -f
```

## Render Update

Set Render backend environment:

```env
FACE_ENGINE=huggingface
HF_FACE_API_URL=http://PUBLIC_IP:7860
HF_FACE_API_TOKEN=same-secret-used-on-oracle
HF_FACE_MODEL=buffalo_s
HF_TIMEOUT_SECONDS=60
```

Redeploy Render after changing the environment variables.
